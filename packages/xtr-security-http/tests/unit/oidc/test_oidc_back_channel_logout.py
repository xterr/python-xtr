"""Recording the session a provider says has ended, on the token it pushed."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_security_core.exception import AuthenticationError

from tests.support.recording_logger import RecordingLogger
from xtr_security_http.oidc.oidc_back_channel_logout import OidcBackChannelLogout
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_ended_sessions import OidcEndedSessions
from xtr_security_http.oidc.oidc_logout_token import OidcLogoutToken
from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import RequestOptions

pytestmark = pytest.mark.anyio

_ISSUER = "https://issuer.example"
_JWKS_URI = "https://issuer.example/jwks.json"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_CLIENT = "shop-api"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)


def _key(kid: str = "k1") -> RSAKey:
    """A fresh RSA signing key carrying ``kid``."""
    return RSAKey.generate_key(2048, parameters={"kid": kid, "use": "sig"})


def _jwks(*keys: object) -> MockResponse:
    """A JWKS answer for ``keys``."""
    return MockResponse(
        json.dumps({"keys": list(keys)}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@final
class _Server:
    """A scripted issuer answering discovery and JWKS from a list of keys."""

    def __init__(self, *answers: MockResponse) -> None:
        self._answers = list(answers)

    def client(self) -> MockHttpClient:
        """A client answering this issuer's paths."""
        answers = self._answers

        def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
            del method, options
            if url == _DOCUMENT_URI:
                return MockResponse(
                    json.dumps({"issuer": _ISSUER, "jwks_uri": _JWKS_URI}).encode(),
                    {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
                )
            if url == _JWKS_URI:
                return answers.pop(0) if answers else _jwks()
            return MockResponse(b"{}", {"http_code": 404})

        return MockHttpClient(answer, base_uri=_ISSUER)


def _logout_token(
    key: RSAKey,
    *,
    issuer: str = _ISSUER,
    audience: str | list[str] = _CLIENT,
    extra: Mapping[str, object] | None = None,
) -> str:
    """Sign a logout token naming the test session."""
    claims: dict[str, object] = {
        "iss": issuer,
        "aud": audience,
        "iat": _NOW,
        "exp": _NOW + 600,
        "jti": "the-logout",
        "events": {OidcLogoutToken.EVENT: {}},
        "sid": "sid-1",
    }
    claims.update(extra or {})
    return jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key)


def _handler(
    server: _Server,
    *,
    client_id: str = _CLIENT,
    logger: RecordingLogger | None = None,
    ended_sessions: OidcEndedSessions | None = None,
) -> OidcBackChannelLogout:
    """The back-channel endpoint over ``server``, its clock frozen at the test instant."""
    frozen = MockClock(_FROZEN)
    client = server.client()
    cache = ArrayAdapter(clock=frozen)
    discovery = OidcDiscovery(client, cache, issuer=_ISSUER)
    verifier = OidcSignatureVerifier(discovery, cache, client, clock=frozen)
    sessions = (
        ended_sessions
        if ended_sessions is not None
        else OidcEndedSessions(ArrayAdapter(clock=frozen), "main", 3600)
    )
    return OidcBackChannelLogout(
        verifier,
        OidcLogoutToken(clock=frozen),
        discovery,
        client_id,
        sessions,
        logger,
    )


async def test_a_verified_token_records_the_session_it_names() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    ended = OidcEndedSessions(ArrayAdapter(clock=MockClock(_FROZEN)), "main", 3600)
    handler = _handler(server, ended_sessions=ended)

    await handler.logout(_logout_token(key))

    assert await ended.has("sid-1")


async def test_a_token_signed_elsewhere_is_refused_with_the_reason_hidden() -> None:
    """The endpoint is public: whoever reaches it learns nothing about the verification."""
    key = _key()
    server = _Server(_jwks(dict(_key(kid="other").as_dict(private=False))))
    logger = RecordingLogger()
    handler = _handler(server, logger=logger)

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout(_logout_token(key))

    assert str(raised.value) == "The logout token could not be verified."
    assert raised.value.__cause__ is not None
    assert logger.messages("warning") == [
        "The back-channel logout token could not be verified.",
    ]


async def test_a_malformed_token_is_refused_with_the_reason_hidden() -> None:
    logger = RecordingLogger()
    handler = _handler(_Server(), logger=logger)

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout("not-a-jwt")

    assert str(raised.value) == "The logout token could not be verified."
    assert logger.messages("warning") == [
        "The back-channel logout token could not be verified.",
    ]


async def test_a_token_refused_by_its_claims_is_refused_as_itself() -> None:
    """The claims say what the provider got wrong; the endpoint is the provider's own to fix."""
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    logger = RecordingLogger()
    handler = _handler(server, logger=logger)

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout(_logout_token(key, audience="other-api"))

    assert 'the audience does not name "shop-api"' in str(raised.value)
    assert logger.messages("warning") == [
        "The back-channel logout token was refused.",
    ]


async def test_the_claims_are_weighed_against_the_announced_issuer() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    handler = _handler(server)

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout(_logout_token(key, issuer="https://other.example"))

    assert "does not match the expected" in str(raised.value)


async def test_the_claims_are_weighed_against_the_client_id() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    handler = _handler(server, client_id="other-client")

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout(_logout_token(key))

    assert 'the audience does not name "other-client"' in str(raised.value)


async def test_a_replayed_logout_token_is_recorded_again() -> None:
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    ended = OidcEndedSessions(ArrayAdapter(clock=MockClock(_FROZEN)), "main", 3600)
    handler = _handler(server, ended_sessions=ended)
    token = _logout_token(key)

    await handler.logout(token)
    await handler.logout(token)

    assert await ended.has("sid-1")


async def test_a_token_naming_a_session_never_opened_is_recorded_anyway() -> None:
    """A provider telling a client about a session it never opened is not an error."""
    key = _key()
    server = _Server(_jwks(dict(key.as_dict(private=False))))
    ended = OidcEndedSessions(ArrayAdapter(clock=MockClock(_FROZEN)), "main", 3600)
    handler = _handler(server, ended_sessions=ended)

    assert not await ended.has("sid-1")
    await handler.logout(_logout_token(key))

    assert await ended.has("sid-1")


async def test_an_unreachable_discovery_document_is_refused_as_itself() -> None:
    """The issuer the claims are weighed against is read inside the refusal's guard."""
    logger = RecordingLogger()
    # The collaborators are concrete classes; the stand-ins below carry the one
    # behaviour each is there to pin — the casts say what the handler's own
    # parameters cannot: that a stand-in answers the same calls.
    handler = OidcBackChannelLogout(
        cast("OidcSignatureVerifier", cast("object", _AcceptingVerifier())),
        OidcLogoutToken(clock=MockClock(_FROZEN)),
        cast("OidcDiscovery", cast("object", _UnreachableDiscovery())),
        _CLIENT,
        OidcEndedSessions(ArrayAdapter(clock=MockClock(_FROZEN)), "main", 3600),
        logger,
    )

    with pytest.raises(AuthenticationError) as raised:
        await handler.logout("any token the verifier takes")

    assert "could not be fetched" in str(raised.value)
    assert logger.messages("warning") == [
        "The back-channel logout token was refused.",
    ]


@final
class _AcceptingVerifier:
    """A verifier that takes every token as the provider's own."""

    async def verify(self, id_token: str) -> dict[str, object]:
        """Answer the claims of a valid logout token, whatever was handed."""
        del id_token
        return {
            "iss": _ISSUER,
            "aud": _CLIENT,
            "iat": _NOW,
            "exp": _NOW + 600,
            "jti": "the-logout",
            "events": {OidcLogoutToken.EVENT: {}},
            "sid": "sid-1",
        }


@final
class _UnreachableDiscovery:
    """A discovery reader whose document cannot be fetched."""

    async def get_configuration(self) -> dict[str, object]:
        """Refuse the read the way an unreachable provider does."""
        raise AuthenticationError(
            f'The OIDC discovery document could not be fetched from "{_DOCUMENT_URI}": no answer.',
        )
