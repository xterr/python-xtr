"""The OAuth2 token handler introspects a token into a user badge."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Final, TypeVar, final

import pytest
from joserfc import jwt
from joserfc.jwk import OctKey
from joserfc.jws import serialize_compact
from xtr_cache import ArrayAdapter, CacheItem
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.exception import TransportError
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import BadMethodCallError, InvalidArgumentError
from xtr_security_core.user.oauth2_user import OAuth2User

from tests.support.oidc import NOW, make_key, make_key_set
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler
from xtr_security_http.authenticator._access_token_scopes import extract_scopes
from xtr_security_http.exception import InvalidAccessTokenError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from joserfc.jwk import RSAKey
    from xtr_cache_contracts import Callback, Metadata
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

_ISSUER: Final = "https://as.example"
_AUDIENCE: Final = "shop-api"
_INTROSPECTION_URI: Final = "https://as.example/introspect"
_JWT_MEDIA_TYPE: Final = "application/token-introspection+jwt"

_T = TypeVar("_T")


def _clock_at(moment: int) -> MockClock:
    """Freeze a clock at the Unix timestamp ``moment`` names."""
    return MockClock(datetime.fromtimestamp(moment, UTC))


def _members(**extra: object) -> dict[str, object]:
    """The members of an active, unexpired introspection response, plus ``extra``."""
    members: dict[str, object] = {"active": True, "sub": "alice", "exp": NOW + 3600}
    members.update(extra)
    return members


def _json_response(members: Mapping[str, object]) -> MockResponse:
    """A plain JSON introspection response carrying ``members``."""
    return MockResponse(
        json.dumps(members).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


def _jwt_response(content: bytes) -> MockResponse:
    """A signed introspection response carrying ``content``."""
    return MockResponse(
        content,
        {"http_code": 200, "response_headers": {"Content-Type": _JWT_MEDIA_TYPE}},
    )


def _mint_introspection(  # noqa: PLR0913 -- a signed response has many claims, each optional
    key: RSAKey,
    members: Mapping[str, object],
    *,
    issuer: str = _ISSUER,
    audience: str | list[str] = _AUDIENCE,
    iat: int = NOW,
    typ: str | None = "token-introspection+jwt",
    extra: Mapping[str, object] | None = None,
) -> bytes:
    """Sign a JWT introspection response wrapping ``members``."""
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "iat": iat,
        "token_introspection": dict(members),
    }
    if extra is not None:
        claims.update(extra)
    header: dict[str, object] = {"alg": "RS256", "kid": key.kid}
    if typ is not None:
        header["typ"] = typ
    return jwt.encode(header, claims, key).encode()


def _client(*responses: MockResponse) -> MockHttpClient:
    """A client answering the introspection endpoint from ``responses``, in order."""
    return MockHttpClient(list(responses), base_uri=_INTROSPECTION_URI)


def _handler(  # noqa: PLR0913 -- a test builder; every knob defaults
    client: HttpClientInterface | None = None,
    *,
    now: int = NOW,
    audiences: str | Sequence[str] = (),
    issuer: str | None = None,
    claim: str | None = None,
    drift: int = 0,
    logger: LoggerInterface | None = None,
) -> Oauth2TokenHandler:
    """A handler over ``client``, frozen at ``now``, expecting what the knobs name."""
    return Oauth2TokenHandler(
        client if client is not None else MockHttpClient(),
        logger,
        audiences,
        issuer,
        claim,
        _clock_at(now),
        drift,
    )


@final
class _RecordingCache:
    """A cache that computes on every call, keeping the keys and items it saw."""

    def __init__(self, clock: MockClock) -> None:
        self._clock = clock
        self.keys: list[str] = []
        self.items: list[CacheItem] = []

    async def get(
        self,
        key: str,
        callback: Callback[_T],
        /,
        *,
        beta: float | None = None,
        metadata: Metadata | None = None,
    ) -> _T:
        """Compute the value, recording the key and the item it was computed for."""
        del beta, metadata
        self.keys.append(key)
        item = CacheItem(key, clock=self._clock)
        self.items.append(item)
        return await callback(item)

    async def delete(self, key: str, /) -> bool:
        """Remove nothing; this cache holds nothing."""
        del key
        return True


def test_an_audience_that_is_not_a_non_empty_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _handler(audiences=("shop-api", ""))


def test_a_non_positive_cache_lifetime_is_refused() -> None:
    handler = _handler()

    with pytest.raises(InvalidArgumentError):
        handler.enable_cache(_RecordingCache(_clock_at(NOW)), "prefix", 0)


def test_an_empty_algorithm_allow_list_is_refused() -> None:
    handler = _handler()
    key = make_key()

    with pytest.raises(InvalidArgumentError):
        handler.enable_signed_response((), make_key_set(key))


@pytest.mark.anyio
async def test_an_active_token_yields_a_badge_with_the_members_as_attributes() -> None:
    members = _members(
        scope="books:read orders:read",
        client_id="web",
        jti="id-1",
    )
    handler = _handler(_client(_json_response(members)))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"
    assert badge.get_attributes() == members
    assert extract_scopes(badge.get_attributes(), ("scope", "scp")) == [
        "books:read",
        "orders:read",
    ]


@pytest.mark.anyio
async def test_the_badge_loader_builds_an_oauth2_user() -> None:
    handler = _handler(
        _client(_json_response(_members(scope="books:read", client_id="web", jti="id-1"))),
    )

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.get_user_identifier() == "alice"
    assert user.sub == "alice"
    assert user.scope == "books:read"
    assert user.client_id == "web"
    assert user.jti == "id-1"
    assert list(user.get_roles()) == ["ROLE_USER"]


@pytest.mark.anyio
async def test_the_loader_drops_empty_and_null_members() -> None:
    handler = _handler(
        _client(_json_response(_members(department="sales", empty="", nothing=None))),
    )

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.additional_claims["department"] == "sales"
    assert "empty" not in user.additional_claims
    assert "nothing" not in user.additional_claims


@pytest.mark.anyio
async def test_a_numeric_updated_at_becomes_the_moment_it_names() -> None:
    handler = _handler(_client(_json_response(_members(updated_at=NOW))))

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.additional_claims["updated_at"] == datetime.fromtimestamp(NOW, UTC)


@pytest.mark.anyio
async def test_a_recognised_verified_flag_is_kept_and_an_unrecognised_one_is_dropped() -> None:
    handler = _handler(
        _client(_json_response(_members(email_verified="yes", phone_number_verified="maybe"))),
    )

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.additional_claims["email_verified"] is True
    assert "phone_number_verified" not in user.additional_claims


@pytest.mark.anyio
async def test_a_verified_flag_reads_a_boolean_and_a_false_spelling() -> None:
    handler = _handler(
        _client(_json_response(_members(email_verified=True, phone_number_verified="off"))),
    )

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.additional_claims["email_verified"] is True
    assert user.additional_claims["phone_number_verified"] is False


@pytest.mark.anyio
async def test_a_verified_flag_reads_the_numbers_one_and_zero() -> None:
    handler = _handler(
        _client(_json_response(_members(email_verified=1, phone_number_verified=0))),
    )

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert user.additional_claims["email_verified"] is True
    assert user.additional_claims["phone_number_verified"] is False


@pytest.mark.anyio
async def test_a_verified_flag_of_an_unrecognised_shape_is_dropped() -> None:
    handler = _handler(_client(_json_response(_members(email_verified=["yes"]))))

    badge = await handler.get_user_badge_from("the-token")
    user = await badge.get_user()

    assert isinstance(user, OAuth2User)
    assert "email_verified" not in user.additional_claims


@pytest.mark.anyio
async def test_a_missing_active_member_is_refused() -> None:
    handler = _handler(_client(_json_response({"sub": "alice"})))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert 'The claim "active" was not found' in str(raised.value)


@pytest.mark.anyio
async def test_a_false_active_member_is_refused() -> None:
    handler = _handler(_client(_json_response({"active": False, "sub": "alice"})))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_a_string_active_member_is_refused() -> None:
    handler = _handler(_client(_json_response({"active": "true", "sub": "alice"})))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_the_public_message_is_always_invalid_credentials() -> None:
    handler = _handler(_client(_json_response({"active": False})))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert raised.value.get_message_key() == "Invalid credentials."


@pytest.mark.anyio
async def test_the_request_carries_the_token_the_hint_and_no_redirects() -> None:
    captured: list[tuple[str, str, Mapping[str, object]]] = []

    def answer(method: str, url: str, options: Mapping[str, object]) -> MockResponse:
        captured.append((method, url, dict(options)))
        return _json_response(_members())

    handler = _handler(MockHttpClient(answer, base_uri=_INTROSPECTION_URI))

    _ = await handler.get_user_badge_from("the-token")

    assert len(captured) == 1
    method, url, options = captured[0]
    assert method == "POST"
    assert url == _INTROSPECTION_URI
    assert options["headers"] == {"Accept": "application/json"}
    assert options["body"] == {"token": "the-token", "token_type_hint": "access_token"}
    assert options["max_redirects"] == 0


@pytest.mark.anyio
async def test_an_expired_token_is_refused() -> None:
    handler = _handler(_client(_json_response(_members(exp=NOW - 10))))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The token reported by the authorization server has expired."


@pytest.mark.anyio
async def test_the_drift_admits_a_just_expired_token() -> None:
    handler = _handler(_client(_json_response(_members(exp=NOW - 5))), drift=30)

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_not_yet_valid_token_is_refused() -> None:
    handler = _handler(_client(_json_response(_members(nbf=NOW + 500))))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The token reported by the authorization server is not valid yet."


@pytest.mark.anyio
async def test_a_token_issued_in_the_future_is_refused() -> None:
    handler = _handler(_client(_json_response(_members(iat=NOW + 500))))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        "The token reported by the authorization server was issued in the future."
    )


@pytest.mark.anyio
async def test_a_non_timestamp_exp_is_refused() -> None:
    handler = _handler(_client(_json_response(_members(exp="soon"))))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        'The "exp" claim reported by the authorization server is not a timestamp.'
    )


@pytest.mark.anyio
async def test_a_numeric_string_exp_is_read_as_the_timestamp_it_names() -> None:
    handler = _handler(_client(_json_response(_members(exp=str(NOW + 3600)))))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_an_exp_of_an_absurd_magnitude_or_a_boolean_is_refused() -> None:
    for value in (1e300, True):
        handler = _handler(_client(_json_response(_members(exp=value))))

        with pytest.raises(InvalidAccessTokenError) as raised:
            _ = await handler.get_user_badge_from("the-token")

        assert str(raised.value) == (
            'The "exp" claim reported by the authorization server is not a timestamp.'
        )


@pytest.mark.anyio
async def test_a_token_from_another_issuer_is_refused() -> None:
    handler = _handler(
        _client(_json_response(_members(iss="https://evil.example"))),
        issuer=_ISSUER,
    )

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        'The token was issued by "https://evil.example", where "https://as.example" was expected.'
    )


@pytest.mark.anyio
async def test_a_response_without_an_issuer_is_refused_when_one_is_expected() -> None:
    handler = _handler(_client(_json_response(_members())), issuer=_ISSUER)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_no_issuer_is_checked_when_none_is_expected() -> None:
    handler = _handler(_client(_json_response(_members(iss="https://evil.example"))))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_token_for_another_audience_is_refused() -> None:
    handler = _handler(
        _client(_json_response(_members(aud="other-api"))),
        audiences=_AUDIENCE,
    )

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == ('The token is not intended for any of the audiences "shop-api".')


@pytest.mark.anyio
async def test_an_audience_list_with_one_match_is_accepted() -> None:
    handler = _handler(
        _client(_json_response(_members(aud=["other-api", _AUDIENCE]))),
        audiences=_AUDIENCE,
    )

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_identifier_comes_from_the_configured_claim() -> None:
    handler = _handler(
        _client(_json_response(_members(email="alice@example.com"))),
        claim="email",
    )

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice@example.com"


@pytest.mark.anyio
async def test_a_missing_configured_claim_is_refused() -> None:
    handler = _handler(_client(_json_response(_members())), claim="email")

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == ('"email" claim not found on the authorization server response.')


@pytest.mark.anyio
async def test_the_username_falls_back_when_sub_is_absent() -> None:
    members = _members()
    del members["sub"]
    members["username"] = "alice"
    handler = _handler(_client(_json_response(members)))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_response_with_neither_sub_nor_username_is_refused() -> None:
    members = _members()
    del members["sub"]
    handler = _handler(_client(_json_response(members)))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        '"sub" and "username" claims not found on the authorization server response. '
        "At least one is required."
    )


@pytest.mark.anyio
async def test_an_integer_identifier_is_accepted() -> None:
    members = _members()
    members["sub"] = 123
    handler = _handler(_client(_json_response(members)))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "123"


@pytest.mark.anyio
async def test_a_transport_failure_is_wrapped_and_logged() -> None:
    logger = RecordingLogger()
    handler = _handler(
        MockHttpClient(
            MockResponse(b"", {"error": "the authorization server is unreachable"}),
            base_uri=_INTROSPECTION_URI,
        ),
        logger=logger,
    )

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert isinstance(raised.value.__cause__, TransportError)
    assert logger.messages("error") == ["An error occurred on the authorization server."]


@pytest.mark.anyio
async def test_a_non_json_body_is_refused() -> None:
    handler = _handler(
        MockHttpClient(
            MockResponse(b"not json", {"response_headers": {"Content-Type": "application/json"}}),
            base_uri=_INTROSPECTION_URI,
        ),
    )

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_an_unsuccessful_status_is_refused() -> None:
    handler = _handler(
        MockHttpClient(
            MockResponse(b'{"active": true}', {"http_code": 500}),
            base_uri=_INTROSPECTION_URI,
        ),
    )

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_a_cached_introspection_answers_the_second_call_without_a_request() -> None:
    client = _client(_json_response(_members()), _json_response(_members()))
    handler = _handler(client)
    handler.enable_cache(ArrayAdapter(), "introspection.", ttl=60)

    first = await handler.get_user_badge_from("the-token")
    second = await handler.get_user_badge_from("the-token")

    assert first.get_user_identifier() == "alice"
    assert second.get_user_identifier() == "alice"
    assert client.get_requests_count() == 1


@pytest.mark.anyio
async def test_an_inactive_response_is_not_cached() -> None:
    client = _client(
        _json_response({"active": False}),
        _json_response({"active": False}),
    )
    handler = _handler(client)
    handler.enable_cache(ArrayAdapter(), "introspection.", ttl=60)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")
    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")

    assert client.get_requests_count() == 2


@pytest.mark.anyio
async def test_the_cache_key_is_the_prefixed_digest_of_the_token() -> None:
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(_client(_json_response(_members())))
    handler.enable_cache(cache, "introspection.", ttl=60)

    _ = await handler.get_user_badge_from("the-token")

    assert cache.keys == [f"introspection.{sha256(b'the-token').hexdigest()}"]


@pytest.mark.anyio
async def test_the_entry_outlives_neither_the_configured_nor_the_reported_lifetime() -> None:
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(_client(_json_response(_members(exp=NOW + 100))))
    handler.enable_cache(cache, "introspection.", ttl=60)

    _ = await handler.get_user_badge_from("the-token")

    assert cache.items[0].expiry == NOW + 60


@pytest.mark.anyio
async def test_the_entry_lives_no_longer_than_the_reported_exp() -> None:
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(_client(_json_response(_members(exp=NOW + 10))))
    handler.enable_cache(cache, "introspection.", ttl=60)

    _ = await handler.get_user_badge_from("the-token")

    assert cache.items[0].expiry == NOW + 10


@pytest.mark.anyio
async def test_an_entry_that_would_outlive_the_token_is_not_kept() -> None:
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(_client(_json_response(_members(exp=NOW - 5))))
    handler.enable_cache(cache, "introspection.", ttl=60)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")

    assert cache.items[0].expiry == NOW


@pytest.mark.anyio
async def test_a_signed_response_is_verified_and_unwrapped() -> None:
    key = make_key()
    handler = _handler(_client(_jwt_response(_mint_introspection(key, _members()))))
    handler.enable_signed_response(("RS256",), make_key_set(key))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_accept_header_offers_only_the_jwt_media_type_when_enforced() -> None:
    captured: list[tuple[str, str, Mapping[str, object]]] = []
    key = make_key()

    def answer(method: str, url: str, options: Mapping[str, object]) -> MockResponse:
        captured.append((method, url, dict(options)))
        return _jwt_response(_mint_introspection(key, _members()))

    handler = _handler(MockHttpClient(answer, base_uri=_INTROSPECTION_URI))
    handler.enable_signed_response(("RS256",), make_key_set(key))

    _ = await handler.get_user_badge_from("the-token")

    assert captured[0][2]["headers"] == {"Accept": _JWT_MEDIA_TYPE}


@pytest.mark.anyio
async def test_the_accept_header_offers_both_media_types_when_not_enforced() -> None:
    captured: list[tuple[str, str, Mapping[str, object]]] = []

    def answer(method: str, url: str, options: Mapping[str, object]) -> MockResponse:
        captured.append((method, url, dict(options)))
        return _json_response(_members())

    key = make_key()
    handler = _handler(MockHttpClient(answer, base_uri=_INTROSPECTION_URI))
    handler.enable_signed_response(("RS256",), make_key_set(key), enforce=False)

    _ = await handler.get_user_badge_from("the-token")

    assert captured[0][2]["headers"] == {"Accept": f"{_JWT_MEDIA_TYPE}, application/json"}


@pytest.mark.anyio
async def test_a_plain_answer_is_refused_when_a_signed_one_is_required() -> None:
    key = make_key()
    handler = _handler(_client(_json_response(_members())))
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        "A signed introspection response is required, but the authorization server "
        'answered with "application/json".'
    )


@pytest.mark.anyio
async def test_a_plain_answer_is_accepted_when_enforcement_is_off() -> None:
    key = make_key()
    handler = _handler(_client(_json_response(_members())))
    handler.enable_signed_response(("RS256",), make_key_set(key), enforce=False)

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_signed_answer_without_verification_configured_is_refused() -> None:
    handler = _handler(_client(_jwt_response(_mint_introspection(make_key(), _members()))))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        "The authorization server returned a JWT introspection response, "
        "which this resource server is not configured to verify."
    )


@pytest.mark.anyio
async def test_a_bad_signature_is_refused() -> None:
    signer = make_key("signer")
    trusted = make_key("trusted")
    handler = _handler(_client(_jwt_response(_mint_introspection(signer, _members()))))
    handler.enable_signed_response(("RS256",), make_key_set(trusted))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The signature of the introspection response is invalid."


@pytest.mark.anyio
async def test_a_malformed_jwt_is_refused() -> None:
    key = make_key()
    handler = _handler(_client(_jwt_response(b"not-a-token")))
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == "The introspection response is not a valid JWT."


@pytest.mark.anyio
async def test_a_wrong_typ_header_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(_jwt_response(_mint_introspection(key, _members(), typ="at+jwt"))),
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        'The "typ" header of the introspection response is not "token-introspection+jwt".'
    )


@pytest.mark.anyio
async def test_a_missing_mandatory_claim_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(_jwt_response(_mint_introspection(key, _members(), extra={"aud": None}))),
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == 'The introspection response is missing the "aud" claim(s).'


@pytest.mark.anyio
async def test_a_future_iat_is_refused_and_admitted_within_the_drift() -> None:
    key = make_key()
    strict = _handler(_client(_jwt_response(_mint_introspection(key, _members(), iat=NOW + 500))))
    strict.enable_signed_response(("RS256",), make_key_set(key))
    lenient = _handler(
        _client(_jwt_response(_mint_introspection(key, _members(), iat=NOW + 500))),
        drift=600,
    )
    lenient.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await strict.get_user_badge_from("the-token")

    assert str(raised.value) == "The introspection response was issued in the future."
    badge = await lenient.get_user_badge_from("the-token")
    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_wrong_top_level_issuer_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(_jwt_response(_mint_introspection(key, _members(), issuer="https://evil.example"))),
        issuer=_ISSUER,
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_a_wrong_top_level_audience_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(_jwt_response(_mint_introspection(key, _members(), audience="other-api"))),
        audiences=_AUDIENCE,
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_an_algorithm_outside_the_allow_list_is_refused() -> None:
    symmetric = OctKey.generate_key(256)
    key = make_key()
    handler = _handler(
        _client(
            _jwt_response(
                jwt.encode(
                    {"alg": "HS256", "typ": "token-introspection+jwt"},
                    {
                        "iss": _ISSUER,
                        "aud": _AUDIENCE,
                        "iat": NOW,
                        "token_introspection": dict(_members()),
                    },
                    symmetric,
                ).encode(),
            ),
        ),
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        "The algorithm of the introspection response is not one of the allowed ones."
    )


@pytest.mark.anyio
async def test_a_payload_that_is_not_a_json_object_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(
            _jwt_response(
                serialize_compact(
                    {"alg": "RS256", "kid": key.kid, "typ": "token-introspection+jwt"},
                    json.dumps(["not", "an", "object"]).encode(),
                    key,
                ).encode(),
            ),
        ),
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == ("The payload of the introspection response is not a JSON object.")


@pytest.mark.anyio
async def test_a_non_object_token_introspection_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(
            _jwt_response(
                jwt.encode(
                    {"alg": "RS256", "kid": key.kid, "typ": "token-introspection+jwt"},
                    {"iss": _ISSUER, "aud": _AUDIENCE, "iat": NOW, "token_introspection": "no"},
                    key,
                ).encode(),
            ),
        ),
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError) as raised:
        _ = await handler.get_user_badge_from("the-token")

    assert str(raised.value) == (
        'The "token_introspection" claim of the introspection response is not a JSON object.'
    )


@pytest.mark.anyio
async def test_the_members_of_a_signed_response_skip_the_repeated_issuer_check() -> None:
    key = make_key()
    handler = _handler(
        _client(_jwt_response(_mint_introspection(key, _members()))),
        issuer=_ISSUER,
        audiences=_AUDIENCE,
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_a_signed_response_whose_members_repeat_a_wrong_issuer_is_refused() -> None:
    key = make_key()
    handler = _handler(
        _client(
            _jwt_response(
                _mint_introspection(key, _members(iss="https://evil.example")),
            ),
        ),
        issuer=_ISSUER,
    )
    handler.enable_signed_response(("RS256",), make_key_set(key))

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


_METADATA_URI: Final = "https://as.example/.well-known/oauth-authorization-server/issue/token"
"""Where RFC 8414 Section 3 reads the issuer's metadata from."""


def _metadata_response(**members: object) -> MockResponse:
    """The authorization server's metadata document, plus ``members``."""
    return MockResponse(
        json.dumps(
            {"issuer": _ISSUER, "jwks_uri": "https://as.example/jwks.json", **members}
        ).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


def _jwks_response(key: RSAKey) -> MockResponse:
    """The authorization server's JWKS, carrying ``key``'s public half."""
    return MockResponse(
        json.dumps({"keys": [dict(key.as_dict(private=False), use="sig")]}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@pytest.mark.anyio
async def test_a_signed_answer_is_verified_against_the_discovered_keys() -> None:
    key = make_key()
    client = MockHttpClient(
        [
            _jwt_response(_mint_introspection(key, _members())),
            _metadata_response(),
            _jwks_response(key),
        ],
        base_uri=_INTROSPECTION_URI,
    )
    handler = _handler(client, audiences=_AUDIENCE, issuer=_ISSUER)
    handler.enable_signed_response(("RS256",))
    handler.enable_signed_response_discovery(ArrayAdapter(clock=_clock_at(NOW)), client, "as")

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_the_metadata_document_is_cached_under_the_suffixed_key() -> None:
    key = make_key()
    client = MockHttpClient(
        [
            _jwt_response(_mint_introspection(key, _members())),
            _metadata_response(),
            _jwks_response(key),
        ],
        base_uri=_INTROSPECTION_URI,
    )
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(client, audiences=_AUDIENCE, issuer=_ISSUER)
    handler.enable_signed_response(("RS256",))
    handler.enable_signed_response_discovery(cache, client, "as")

    _ = await handler.get_user_badge_from("the-token")

    # The keys are asked for first; the metadata document is read inside that
    # computation, so its own entry follows.
    assert cache.keys == ["as", "as.document"]


@pytest.mark.anyio
async def test_the_keys_are_cached_under_the_bare_key() -> None:
    key = make_key()
    client = MockHttpClient(
        [
            _jwt_response(_mint_introspection(key, _members())),
            _metadata_response(),
            _jwks_response(key),
        ],
        base_uri=_INTROSPECTION_URI,
    )
    cache = _RecordingCache(_clock_at(NOW))
    handler = _handler(client, audiences=_AUDIENCE, issuer=_ISSUER)
    handler.enable_signed_response(("RS256",))
    handler.enable_signed_response_discovery(cache, client, "as")

    _ = await handler.get_user_badge_from("the-token")

    assert "as" in cache.keys


@pytest.mark.anyio
async def test_a_signed_answer_without_any_key_source_is_refused() -> None:
    client = MockHttpClient([_jwt_response(_mint_introspection(make_key(), _members()))])
    handler = _handler(client, audiences=_AUDIENCE, issuer=_ISSUER)
    handler.enable_signed_response(("RS256",), None)

    with pytest.raises(InvalidAccessTokenError):
        _ = await handler.get_user_badge_from("the-token")


@pytest.mark.anyio
async def test_a_plain_answer_is_accepted_without_any_key_source() -> None:
    client = MockHttpClient([_json_response(_members())])
    handler = _handler(client)
    handler.enable_signed_response(("RS256",), None)

    badge = await handler.get_user_badge_from("the-token")

    assert badge.get_user_identifier() == "alice"


def test_the_discovery_path_refuses_a_handler_without_an_issuer() -> None:
    handler = _handler(MockHttpClient())

    with pytest.raises(BadMethodCallError):
        handler.enable_signed_response_discovery(ArrayAdapter(), MockHttpClient(), "as")


def test_the_metadata_url_inserts_the_well_known_path() -> None:
    from xtr_security_http.access_token.oauth2.oauth2_token_handler import (  # noqa: PLC0415 -- test-local helper
        _metadata_url,
    )

    assert _metadata_url("https://as.example/issue/token") == _METADATA_URI
    assert _metadata_url("https://as.example/issue/token/") == _METADATA_URI
    assert _metadata_url("https://as.example") == (
        "https://as.example/.well-known/oauth-authorization-server"
    )


def test_a_non_url_issuer_is_refused_by_the_metadata_url() -> None:
    from xtr_security_http.access_token.oauth2.oauth2_token_handler import (  # noqa: PLC0415 -- test-local helper
        _metadata_url,
    )

    with pytest.raises(BadMethodCallError):
        _ = _metadata_url("issuer.example")
