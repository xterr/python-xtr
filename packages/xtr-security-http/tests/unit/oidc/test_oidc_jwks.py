"""The JWKS reader weighs keys and freshness the way RFC 9111 leaves them."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc.jwk import RSAKey
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oidc.oidc_jwks import OidcJwks

if TYPE_CHECKING:
    from xtr_cache_contracts import ItemInterface
    from xtr_http_client_contracts import HttpResponseInterface

_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)
_JWKS_URI = "https://issuer.example/jwks.json"


def _key(
    kid: str = "k1", use: str | None = None, key_ops: list[str] | None = None
) -> dict[str, object]:
    """A JWK carrying ``kid`` and whatever usage the test declares, generated fresh."""
    exported: dict[str, object] = dict(
        RSAKey.generate_key(2048, parameters={"kid": kid}).as_dict(private=False),
    )
    if use is not None:
        exported["use"] = use
    if key_ops is not None:
        exported["key_ops"] = key_ops
    return exported


def _response(
    keys: object,
    headers: dict[str, str] | None = None,
    *,
    status: int = 200,
) -> MockResponse:
    """A JWKS answer for ``keys`` with ``headers``."""
    return MockResponse(
        json.dumps(keys).encode(),
        {
            "http_code": status,
            "response_headers": {"Content-Type": "application/json", **(headers or {})},
        },
    )


def _at(seconds: int) -> str:
    """The HTTP date ``seconds`` from the frozen clock's instant."""
    return format_datetime(datetime.fromtimestamp(_NOW + seconds, tz=UTC), usegmt=True)


async def _issued(response: MockResponse) -> HttpResponseInterface:
    """Issue ``response`` through a client, as a real transfer would."""
    return await MockHttpClient([response], base_uri="https://issuer.example").request(
        "GET",
        _JWKS_URI,
    )


async def _read(
    keys: object,
    headers: dict[str, str] | None = None,
    *,
    strict: bool = True,
) -> tuple[list[dict[str, object]], int | None]:
    """Read a JWKS answer for ``keys`` off a response issued through a client."""
    return await OidcJwks.from_response(
        await _issued(_response(keys, headers)),
        strict,
        MockClock(_FROZEN),
    )


@pytest.mark.anyio
async def test_max_age_is_returned_as_the_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    assert await _read({"keys": keys}, {"Cache-Control": "max-age=600"}) == (keys, 600)


@pytest.mark.anyio
async def test_the_age_header_subtracts_from_the_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "max-age=600", "Age": "100"})

    assert ttl == 500


@pytest.mark.anyio
async def test_the_date_subtracts_from_the_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "max-age=600", "Date": _at(-200)})

    assert ttl == 400


@pytest.mark.anyio
async def test_expires_counts_from_the_date() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Date": _at(0), "Expires": _at(300)})

    assert ttl == 300


@pytest.mark.anyio
async def test_expires_without_a_date_counts_from_the_clock() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Expires": _at(120)})

    assert ttl == 120


@pytest.mark.anyio
async def test_a_stale_answer_leaves_no_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "max-age=600", "Age": "600"})

    assert ttl is None


@pytest.mark.anyio
async def test_no_freshness_headers_leave_no_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys)

    assert ttl is None


@pytest.mark.anyio
async def test_an_oversized_jwks_is_refused() -> None:
    response = MockResponse(
        b"x" * (1024 * 1024 + 1),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await OidcJwks.from_response(await _issued(response))

    assert str(raised.value) == "The OIDC provider JWKS exceeds the maximum size of 1 MiB."


@pytest.mark.anyio
async def test_a_jwks_that_is_not_json_is_refused() -> None:
    response = MockResponse(b"not json", {"http_code": 200})

    with pytest.raises(AuthenticationError) as raised:
        _ = await OidcJwks.from_response(await _issued(response))

    assert "invalid JSON" in str(raised.value)


@pytest.mark.anyio
async def test_a_transport_failure_is_refused() -> None:
    client = MockHttpClient(
        [MockResponse(b"", {"error": "no answer"})], base_uri="https://issuer.example"
    )

    with pytest.raises(AuthenticationError):
        _ = await OidcJwks.fetch_keys(
            client,
            _JWKS_URI,
            cast("ItemInterface", cast("object", _RecordingItem())),
            clock=MockClock(_FROZEN),
        )


@pytest.mark.anyio
async def test_a_response_that_fails_to_read_is_refused() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = await OidcJwks.from_response(
            cast("HttpResponseInterface", cast("object", _UnreadableResponse())),
        )

    assert "could not be fetched" in str(raised.value)


@pytest.mark.anyio
async def test_a_non_numeric_age_header_is_read_as_zero() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "max-age=600", "Age": "soon"})

    assert ttl == 600


@pytest.mark.anyio
async def test_a_malformed_date_is_ignored() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "max-age=600", "Date": "not a date"})

    assert ttl == 600


@pytest.mark.anyio
async def test_a_cache_control_without_max_age_falls_to_expires() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Cache-Control": "no-store", "Expires": _at(120)})

    assert ttl == 120


@pytest.mark.anyio
async def test_a_malformed_expires_leaves_no_ttl() -> None:
    keys = [_key(kid="k1", use="sig")]

    _, ttl = await _read(keys, {"Expires": "not a date"})

    assert ttl is None


@pytest.mark.anyio
async def test_a_key_ops_member_that_is_not_a_list_is_dropped() -> None:
    keys = [
        _key(kid="ops", key_ops=["sign", "verify"]),
        _key(kid="weird", key_ops=["sign", "verify"]),
    ]
    keys[1]["key_ops"] = "sign"

    kept, _ = await _read({"keys": keys}, strict=True)

    assert [key["kid"] for key in kept] == ["ops"]


@final
class _UnreadableResponse:
    """A response whose body cannot be read off the transfer."""

    def get_info(self, key: str | None = None) -> object:
        """Name the URL the transfer was made to."""
        del key
        return _JWKS_URI

    def get_header(self, name: str) -> list[str]:
        """Carry no headers."""
        del name
        return []

    async def get_content(self, throw: bool = True) -> bytes:
        """Fail, as a transfer that broke mid-body does."""
        del throw
        raise RuntimeError("the transfer broke")

    async def cancel(self) -> None:
        """Abandon nothing; the transfer already failed."""

    async def __aenter__(self) -> _UnreadableResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close nothing; the transfer already failed."""


@pytest.mark.anyio
async def test_strict_keeps_only_keys_declared_for_signatures() -> None:
    keys = [
        _key(kid="sig", use="sig"),
        _key(kid="enc", use="enc"),
        _key(kid="ops", key_ops=["sign", "verify"]),
        _key(kid="enc-ops", key_ops=["encrypt", "decrypt"]),
        _key(kid="bare"),
    ]

    kept, _ = await _read({"keys": keys}, strict=True)

    assert [key["kid"] for key in kept] == ["sig", "ops"]


@pytest.mark.anyio
async def test_lax_keeps_keys_missing_both_declarations() -> None:
    keys = [
        _key(kid="bare"),
        _key(kid="enc", use="enc"),
        _key(kid="enc-ops", key_ops=["encrypt", "decrypt"]),
        _key(kid="sig-ops", key_ops=["sign", "verify"]),
        _key(kid="both", key_ops=["sign", "encrypt"]),
    ]

    kept, _ = await _read({"keys": keys}, strict=False)

    assert [key["kid"] for key in kept] == ["bare", "sig-ops", "both"]


@pytest.mark.anyio
async def test_a_key_without_a_kty_is_dropped() -> None:
    keys = [{"kid": "no-kty"}, _key(kid="sig", use="sig")]

    kept, _ = await _read({"keys": keys}, strict=False)

    assert [key["kid"] for key in kept] == ["sig"]


@pytest.mark.anyio
async def test_a_key_with_a_non_string_kid_is_dropped() -> None:
    keys = [{"kty": "RSA", "kid": 7}, _key(kid="sig", use="sig")]

    kept, _ = await _read({"keys": keys}, strict=False)

    assert [key["kid"] for key in kept] == ["sig"]


@pytest.mark.anyio
async def test_a_keys_member_that_is_not_a_list_yields_no_keys() -> None:
    kept, _ = await _read({"keys": "not a list"})

    assert kept == []


@final
class _RecordingItem:
    """A cache item that records the lifetime it is given."""

    ttls: list[float | None]

    def __init__(self) -> None:
        self.ttls = []

    def expires_after(self, ttl: float | None) -> _RecordingItem:
        """Record the lifetime, chaining as the contract does."""
        self.ttls.append(ttl)
        return self


@pytest.mark.anyio
async def test_fetch_keys_sets_the_advertised_ttl_on_the_item() -> None:
    item = _RecordingItem()
    client = MockHttpClient(
        [_response({"keys": [_key(kid="k1", use="sig")]}, {"Cache-Control": "max-age=600"})],
        base_uri="https://issuer.example",
    )

    keys = await OidcJwks.fetch_keys(
        client, _JWKS_URI, cast("ItemInterface", cast("object", item)), clock=MockClock(_FROZEN)
    )

    assert [key["kid"] for key in keys] == ["k1"]
    assert item.ttls == [600]


@pytest.mark.anyio
async def test_fetch_keys_falls_back_to_the_default_ttl() -> None:
    item = _RecordingItem()
    client = MockHttpClient(
        [_response([_key(kid="k1", use="sig")])],
        base_uri="https://issuer.example",
    )

    _ = await OidcJwks.fetch_keys(
        client,
        _JWKS_URI,
        cast("ItemInterface", cast("object", item)),
        default_ttl=1200,
        clock=MockClock(_FROZEN),
    )

    assert item.ttls == [1200]


@pytest.mark.anyio
async def test_fetch_keys_caps_the_ttl_at_thirty_days() -> None:
    item = _RecordingItem()
    client = MockHttpClient(
        [
            _response(
                [_key(kid="k1", use="sig")], {"Cache-Control": f"max-age={OidcJwks.MAX_TTL * 2}"}
            )
        ],
        base_uri="https://issuer.example",
    )

    _ = await OidcJwks.fetch_keys(
        client, _JWKS_URI, cast("ItemInterface", cast("object", item)), clock=MockClock(_FROZEN)
    )

    assert item.ttls == [OidcJwks.MAX_TTL]
