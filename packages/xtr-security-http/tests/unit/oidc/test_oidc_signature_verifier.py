"""The signature verifier checks the alg, the keys and the rotation cooldown."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions

_ISSUER = "https://issuer.example"
_JWKS_URI = "https://issuer.example/jwks.json"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


def _key(kid: str = "k1", use: str = "sig") -> RSAKey:
    """A fresh RSA signing key carrying ``kid``."""
    return RSAKey.generate_key(2048, parameters={"kid": kid, "use": use})


def _jwks(*keys: object) -> MockResponse:
    """A JWKS answer for ``keys``."""
    return MockResponse(
        json.dumps({"keys": list(keys)}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


def _document() -> MockResponse:
    """The test issuer's discovery document."""
    return MockResponse(
        json.dumps({"issuer": _ISSUER, "jwks_uri": _JWKS_URI}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@final
class _Server:
    """A scripted issuer answering discovery and JWKS from a list of keys."""

    def __init__(self, *answers: MockResponse) -> None:
        self._answers = list(answers)
        self.jwks_requests = 0

    def client(self) -> MockHttpClient:
        """A client answering this issuer's paths."""
        server = self

        def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
            del method, options
            if url == _DOCUMENT_URI:
                return _document()
            if url == _JWKS_URI:
                server.jwks_requests += 1
                return server._answers.pop(0) if server._answers else _jwks()
            return MockResponse(b"{}", {"http_code": 404})

        return MockHttpClient(answer, base_uri=_ISSUER)


def _verifier(
    server: _Server,
    *,
    algorithms: tuple[str, ...] = ("RS256",),
    clock: MockClock | None = None,
) -> OidcSignatureVerifier:
    """A verifier over ``server``, its clock frozen at the test instant."""
    frozen = clock if clock is not None else MockClock(_FROZEN)
    client = server.client()
    cache = ArrayAdapter(clock=frozen)
    discovery = OidcDiscovery(client, cache, issuer=_ISSUER)
    return OidcSignatureVerifier(
        discovery,
        cache,
        client,
        algorithms,
        clock=frozen,
    )


@pytest.mark.anyio
async def test_it_verifies_a_token_signed_with_the_default_algorithm() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    token = jwt.encode({"alg": "RS256", "kid": key.kid}, {"sub": "alice"}, key)

    claims = await verifier.verify(token)

    assert claims == {"sub": "alice"}


@pytest.mark.anyio
async def test_a_token_signed_with_another_algorithm_is_refused() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    token = _reheader(jwt.encode({"alg": "RS256", "kid": key.kid}, {"sub": "alice"}, key), "PS256")

    with pytest.raises(AuthenticationError) as raised:
        _ = await verifier.verify(token)

    assert "not signed with any of the expected algorithms" in str(raised.value)


def _reheader(token: str, alg: str) -> str:
    """Rewrite a compact token's ``alg`` header, leaving the rest as it stands."""
    import base64  # noqa: PLC0415 -- test-local helpers
    import json as _json  # noqa: PLC0415 -- test-local helpers

    header, payload, signature = token.split(".")
    padded = header + "=" * (-len(header) % 4)
    rewritten = cast(
        "dict[str, object]", cast("object", _json.loads(base64.urlsafe_b64decode(padded)))
    )
    rewritten["alg"] = alg
    encoded = base64.urlsafe_b64encode(_json.dumps(rewritten).encode()).rstrip(b"=").decode()
    return f"{encoded}.{payload}.{signature}"


@pytest.mark.anyio
async def test_a_mac_algorithm_is_never_accepted_whatever_the_keys_hold() -> None:
    secret = OctKey.generate_key(256)
    server = _Server(_jwks(dict(secret.as_dict(private=False))))
    verifier = _verifier(server)
    token = jwt.encode({"alg": "HS256"}, {"sub": "alice"}, secret)

    with pytest.raises(AuthenticationError) as raised:
        _ = await verifier.verify(token)

    assert "not signed with any of the expected algorithms" in str(raised.value)


def test_a_mac_algorithm_in_the_allow_list_is_refused_at_construction() -> None:
    with pytest.raises(AuthenticationError) as raised:
        _ = OidcSignatureVerifier(
            OidcDiscovery(MockHttpClient(), ArrayAdapter(), issuer=_ISSUER),
            ArrayAdapter(),
            MockHttpClient(),
            ("HS256",),
        )

    assert "Unsupported OIDC ID token signature algorithm" in str(raised.value)


@pytest.mark.anyio
async def test_a_malformed_token_is_refused() -> None:
    verifier = _verifier(_Server())

    with pytest.raises(AuthenticationError):
        _ = await verifier.verify("not-a-jwt")


@pytest.mark.anyio
async def test_a_wrong_signature_is_refused() -> None:
    other = _key(kid="other")
    server = _Server(_jwks(dict(other.as_dict(private=False))))
    verifier = _verifier(server)
    signed_elsewhere = jwt.encode(
        {"alg": "RS256", "kid": "elsewhere"}, {"sub": "alice"}, _key(kid="elsewhere")
    )

    with pytest.raises(AuthenticationError):
        _ = await verifier.verify(signed_elsewhere)


@pytest.mark.anyio
async def test_a_document_without_a_jwks_uri_is_refused() -> None:
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps({"issuer": _ISSUER}).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    verifier = OidcSignatureVerifier(
        OidcDiscovery(client, ArrayAdapter(), issuer=_ISSUER),
        ArrayAdapter(),
        client,
        clock=MockClock(_FROZEN),
    )
    token = jwt.encode({"alg": "RS256"}, {"sub": "alice"}, _key())

    with pytest.raises(AuthenticationError) as raised:
        _ = await verifier.verify(token)

    assert "does not announce any" in str(raised.value)


@pytest.mark.anyio
async def test_a_kid_rotation_refetches_past_the_cooldown() -> None:
    old = _key(kid="old")
    rotated = _key(kid="new")
    server = _Server(_jwks(dict(old.as_dict(private=False))))
    clock = MockClock(_FROZEN)
    verifier = _verifier(server, clock=clock)
    token = jwt.encode({"alg": "RS256", "kid": rotated.kid}, {"sub": "alice"}, rotated)

    with pytest.raises(AuthenticationError):
        _ = await verifier.verify(token)
    assert server.jwks_requests == 1

    # Within the cooldown the unknown kid is refused without a second fetch.
    with pytest.raises(AuthenticationError):
        _ = await verifier.verify(token)
    assert server.jwks_requests == 1

    # Past the cooldown the JWKS is refetched, and the rotated key verifies.
    server._answers.append(_jwks(dict(rotated.as_dict(private=False))))
    clock.sleep(OidcSignatureVerifier.ROTATION_COOLDOWN + 1)
    claims = await verifier.verify(token)

    assert claims == {"sub": "alice"}
    assert server.jwks_requests == 2


@pytest.mark.anyio
async def test_a_known_kid_never_refetches() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    token = jwt.encode({"alg": "RS256", "kid": key.kid}, {"sub": "alice"}, key)

    _ = await verifier.verify(token)
    _ = await verifier.verify(token)

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_a_payload_that_is_not_an_object_is_refused() -> None:
    from joserfc import jws  # noqa: PLC0415 -- test-local helpers

    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    token = jws.serialize_compact({"alg": "RS256", "kid": key.kid}, b"[1, 2, 3]", key)

    with pytest.raises(AuthenticationError):
        _ = await verifier.verify(token)


@pytest.mark.anyio
async def test_a_non_string_kid_header_is_refused() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    # The library refuses to sign a non-string kid, so the token carrying one
    # is written by hand: the reader still weighs what it reads.
    import base64  # noqa: PLC0415 -- test-local helper
    import json as _json  # noqa: PLC0415 -- test-local helper

    header = base64.urlsafe_b64encode(_json.dumps({"alg": "RS256", "kid": 7}).encode())
    token = f"{header.rstrip(b'=').decode()}.e30.Zm9v"

    with pytest.raises(AuthenticationError) as raised:
        _ = await verifier.verify(token)

    assert '"kid" header must be a string' in str(raised.value)


@pytest.mark.anyio
async def test_a_jwks_of_only_encryption_keys_is_refused() -> None:
    server = _Server(_jwks({"kty": "RSA", "kid": "enc", "use": "enc"}))
    verifier = _verifier(server)
    token = jwt.encode({"alg": "RS256", "kid": "enc"}, {"sub": "alice"}, _key(kid="enc"))

    with pytest.raises(AuthenticationError) as raised:
        _ = await verifier.verify(token)

    assert "no signing key" in str(raised.value)


@pytest.mark.anyio
async def test_the_keys_are_cached_between_verifications() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    verifier = _verifier(server)
    token = jwt.encode({"alg": "RS256", "kid": key.kid}, {"sub": "alice"}, key)

    _ = await verifier.verify(token)
    _ = await verifier.verify(token)

    assert server.jwks_requests == 1


@pytest.mark.anyio
async def test_lax_filtering_reads_keys_without_usage() -> None:
    bare = RSAKey.generate_key(2048, parameters={"kid": "bare"})
    server = _Server(_jwks(dict(bare.as_dict(private=False))))
    frozen = MockClock(_FROZEN)
    client = server.client()
    cache = ArrayAdapter(clock=frozen)
    verifier = OidcSignatureVerifier(
        OidcDiscovery(client, cache, issuer=_ISSUER),
        cache,
        client,
        enforce_key_usage_verification=False,
        clock=frozen,
    )
    token = jwt.encode({"alg": "RS256", "kid": "bare"}, {"sub": "alice"}, bare)

    claims = await verifier.verify(token)

    assert claims == {"sub": "alice"}
