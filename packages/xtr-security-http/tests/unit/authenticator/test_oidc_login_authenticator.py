"""The OIDC login authenticator: the authorization round trip, end to end."""

from __future__ import annotations

import json
from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, TypeVar, cast, final
from urllib.parse import parse_qsl, urlsplit

import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from typing_extensions import override
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import AuthenticationError, InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.dispatchers import RecordingDispatcher
from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.oidc_login_authenticator import OidcLoginAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.event.oidc_authorization_request_event import (
    OidcAuthorizationRequestEvent,
)
from xtr_security_http.exception import MissingSessionError
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
from xtr_security_http.oidc.oidc_id_token import OidcIdToken
from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpResponseInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authenticator.passport.passport import Passport

_ISSUER = "https://issuer.example"
_CLIENT_ID = "client-1"
_CHECK_PATH = "/oidc/callback"
_NOW = 1_000_000
_FROZEN = datetime.fromtimestamp(_NOW, tz=UTC)
_AUTHORIZATION_ENDPOINT = "https://issuer.example/authorize"
_JWKS_URI = "https://issuer.example/jwks"
_PREFIX = "_security.oidc_login.main."

pytestmark = pytest.mark.anyio

_EventT = TypeVar("_EventT")


def _key(kid: str = "k1") -> RSAKey:
    """A fresh RSA signing key."""
    return RSAKey.generate_key(2048, parameters={"kid": kid, "use": "sig"})


def _id_token(key: RSAKey, **claims: object) -> str:
    """A signed ID token carrying ``claims``, for the frozen clock."""
    return jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {
            "iss": _ISSUER,
            "aud": _CLIENT_ID,
            "sub": "alice",
            "iat": _NOW,
            "exp": _NOW + 3600,
            **claims,
        },
        key,
    )


def _jwks_response(key: RSAKey) -> MockResponse:
    """The public JWKS document for ``key``."""
    return MockResponse(
        json.dumps({"keys": [key.as_dict(private=False)]}).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


def _document(**members: object) -> dict[str, object]:
    """A discovery document for the test issuer, plus ``members``."""
    return {
        "issuer": _ISSUER,
        "authorization_endpoint": _AUTHORIZATION_ENDPOINT,
        "token_endpoint": "https://issuer.example/token",
        "userinfo_endpoint": "https://issuer.example/userinfo",
        "jwks_uri": _JWKS_URI,
        **members,
    }


def _json_response(body: object) -> MockResponse:
    """A JSON answer carrying ``body``."""
    return MockResponse(
        json.dumps(body).encode(),
        {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
    )


@final
class _ScriptedClient(OidcClientInterface):
    """An OIDC client that records what it is asked and mints its answers.

    Given a signing key, the exchange answer carries an ID token minted on
    the spot, carrying the nonce the authorization request sent; a verbatim
    ``answer`` replaces the whole answer, for the tests that need one without
    an ID token or an access token.
    """

    def __init__(  # noqa: PLR0913 -- a test script, naming every part of an answer it can shape
        self,
        key: RSAKey | None = None,
        answer: Mapping[str, object] | None = None,
        claims: Mapping[str, object] | None = None,
        extra: Mapping[str, object] | None = None,
        user_info: Mapping[str, object] | None = None,
        *,
        method: str = "client_secret_basic",
    ) -> None:
        self.exchanges: list[tuple[str, str, str | None]] = []
        self.user_info_calls: list[str] = []
        self._key = key
        self._answer = dict(answer) if answer is not None else None
        self._claims = dict(claims or {})
        self._extra = dict(extra or {})
        self._nonce: str | None = None
        self._user_info = dict(user_info or {"sub": "alice"})
        self._method = method
        self.last_id_token: str | None = None

    def remember_nonce(self, nonce: str) -> None:
        """Record the nonce the authorization request sent."""
        self._nonce = nonce

    @override
    async def request(
        self,
        endpoint: str,
        body: Mapping[str, object] | None = None,
        options: Mapping[str, object] | None = None,
    ) -> HttpResponseInterface:
        """Never reached: the login flow goes through the named operations."""
        raise AssertionError("the login flow makes no raw request")

    @override
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, object]:
        """Record the exchange and answer, minting the ID token when a key was given."""
        self.exchanges.append((code, redirect_uri, code_verifier))
        if self._answer is not None:
            return dict(self._answer)
        data: dict[str, object] = {"token_type": "Bearer", "access_token": "at-1"}
        if self._key is not None:
            claims = {"nonce": self._nonce, **self._claims}
            data["id_token"] = _id_token(self._key, **claims)
            self.last_id_token = str(data["id_token"])
        data.update(self._extra)
        return data

    @override
    async def refresh_token(
        self,
        refresh_token: str,
        scopes: object = (),
    ) -> dict[str, object]:
        """Never reached: the login flow does not refresh."""
        raise AssertionError("the login flow does not refresh")

    @override
    async def fetch_user_info(self, access_token: str) -> dict[str, object]:
        """Record the access token and answer from the script."""
        self.user_info_calls.append(access_token)
        return dict(self._user_info)

    @override
    def get_client_authentication_method(self) -> str:
        """Name the method the script configured."""
        return self._method


@final
class _Provider:
    """A user provider that hands back a user for any identifier."""

    def __init__(self) -> None:
        self.loaded: list[str] = []

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Hand back an enabled user carrying the identifier."""
        self.loaded.append(identifier)
        return InMemoryUser(
            identifier,
            password="hashed",  # noqa: S106 -- a test fixture, not a secret
            roles=("ROLE_USER",),
        )

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Hand the user back as it is; the test never reaches this."""
        return user

    def supports_class(self, user_class: type) -> bool:
        """Answer yes; the test never reaches this."""
        del user_class
        return True


@final
class _Success:
    """A success handler that answers with a fixed response."""

    def __init__(self) -> None:
        self.tokens: list[object] = []

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: object,
    ) -> ResponseInterface:
        """Record the token, and answer with a response of the handler's own."""
        del request
        self.tokens.append(token)
        return ResponseFactory().create_response(200)


@final
class _Failure:
    """A failure handler that answers with a fixed response."""

    def __init__(self) -> None:
        self.errors: list[AuthenticationError] = []

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Record the error, and answer with a response of the handler's own."""
        del request
        self.errors.append(error)
        return ResponseFactory().create_response(401)


@final
class _ListenerDispatcher:
    """A dispatcher that hands each event to a listener before returning it."""

    def __init__(self, listener: Callable[[object], None]) -> None:
        self._listener = listener
        self.events: list[object] = []

    async def dispatch(
        self,
        event: _EventT,
        event_name: str | type | None = None,
    ) -> _EventT:
        """Run the listener on ``event``, then record it."""
        del event_name
        self.events.append(event)
        self._listener(event)
        return event


@final
class _BearerToken(AbstractToken):
    """A bare token carrying attributes, the way the firewall stores one."""


def _discovery(document: Mapping[str, object] | None = None) -> OidcDiscovery:
    """A discovery reader answering the test document."""
    answered = dict(document or _document())

    def answer(method: str, url: str, options: object) -> MockResponse:
        del method, url, options
        return _json_response(answered)

    return OidcDiscovery(
        MockHttpClient(answer, base_uri=_ISSUER),
        ArrayAdapter(),
        issuer=_ISSUER,
        cache_ttl=None,
    )


def _verifier(key: RSAKey) -> OidcSignatureVerifier:
    """A signature verifier serving ``key``'s public JWKS."""
    return OidcSignatureVerifier(
        _discovery(),
        ArrayAdapter(),
        MockHttpClient([_jwks_response(key)], base_uri=_ISSUER),
        ("RS256",),
        clock=MockClock(_FROZEN),
    )


def _session() -> Session:
    """A session on the in-memory storage."""
    return Session(MemorySessionStorage())


def _request(
    session: Session,
    *,
    method: str = "GET",
    path: str = _CHECK_PATH,
    query: str = "",
    parsed_body: object | None = None,
) -> ServerRequestInterface:
    """Build a request whose security state carries ``session``."""
    bag: dict[str, object] = {}
    message = make_message(
        method=method,
        path=path,
        query=query,
        parsed_body=parsed_body,
    ).with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message


def _authenticator(
    client: OidcClientInterface,
    *,
    options: Mapping[str, object] | None = None,
    authorization_params: Mapping[str, str] | None = None,
    signature_verifier: OidcSignatureVerifier | None = None,
    dispatcher: EventDispatcherInterface | None = None,
) -> tuple[OidcLoginAuthenticator, _Provider, _Success, _Failure]:
    """An authenticator over the scripted client and the test discovery."""
    provider = _Provider()
    success = _Success()
    failure = _Failure()
    authenticator = OidcLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        provider,
        client,
        _discovery(),
        OidcIdToken(clock=MockClock(_FROZEN)),
        _CLIENT_ID,
        success,
        failure,
        options=options,
        authorization_params=authorization_params,
        signature_verifier=signature_verifier,
        clock=MockClock(_FROZEN),
        event_dispatcher=dispatcher,
    )
    return authenticator, provider, success, failure


def _location(response: ResponseInterface) -> str:
    """The Location header of a redirect."""
    return response.get_header_line("Location")


def _params_of(response: ResponseInterface) -> dict[str, str]:
    """The query parameters of a redirect's Location, single-valued."""
    return dict(parse_qsl(urlsplit(_location(response)).query))


async def _start(
    authenticator: OidcLoginAuthenticator,
    session: Session,
    *,
    method: str = "GET",
    path: str = "/",
) -> ResponseInterface:
    """Start a login on a request carrying ``session``."""
    return await authenticator.start(_request(session, method=method, path=path))


async def _states_of(session: Session) -> list[str]:
    """The pending attempt states, oldest first, as the session indexes them."""
    states = await session.get(f"{_PREFIX}attempts")
    return cast("list[str]", states) if isinstance(states, list) else []


async def _login(  # noqa: PLR0913 -- a test builder, naming every part of a callback it can shape
    authenticator: OidcLoginAuthenticator,
    client: _ScriptedClient,
    session: Session,
    *,
    extra_query: str = "",
    parsed_body: object | None = None,
    method: str = "GET",
) -> tuple[Passport, str]:
    """Start a login and consume its callback, returning the passport and the state."""
    response = await _start(authenticator, session)
    params = _params_of(response)
    state = params["state"]
    attempt = await session.get(f"{_PREFIX}attempt.{state}")
    assert isinstance(attempt, dict)
    client.remember_nonce(cast("str", attempt["nonce"]))
    query = f"state={state}&code=the-code{extra_query}"
    callback = _request(
        session,
        method=method,
        query="" if parsed_body is not None else query,
        parsed_body=parsed_body,
    )
    passport = await authenticator.authenticate(callback)
    return passport, state


# ---- construction and options ----


def test_an_invalid_pkce_method_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = _authenticator(_ScriptedClient(), options={"pkce_method": "S512"})

    assert "RFC 7636" in str(raised.value)


def test_a_managed_authorization_param_is_refused_at_construction() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = _authenticator(_ScriptedClient(), authorization_params={"state": "mine"})

    assert '"state"' in str(raised.value)


def test_the_dpop_thumbprint_is_managed_though_no_proof_factory_exists() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _authenticator(_ScriptedClient(), authorization_params={"dpop_jkt": "a-thumbprint"})


# ---- supports ----


def test_supports_handles_the_check_path() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    assert authenticator.supports(_request(_session())) is True


def test_supports_refuses_another_path_and_explains_itself() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    reasons = UnsupportedReasons()
    request = _request(_session(), path="/elsewhere").with_attribute(
        SecurityRequestAttributes.UNSUPPORTED_REASONS,
        reasons,
    )

    assert authenticator.supports(request) is False
    assert reasons.all() == (
        f'the request path "/elsewhere" does not match the "check_path" option "{_CHECK_PATH}"',
    )


def test_a_configured_check_path_is_matched() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        options={"check_path": "/cb"},
    )

    assert authenticator.supports(_request(_session(), path="/cb")) is True
    assert authenticator.supports(_request(_session(), path=_CHECK_PATH)) is False


def test_a_scope_that_is_no_string_nor_sequence_falls_back_to_openid() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient(), options={"scope": None})

    assert authenticator._options.scope == ("openid",)


def test_a_scope_given_as_one_string_is_kept_whole_and_split_by_scopes() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        options={"scope": "email profile"},
    )

    assert authenticator._options.scope == ("email profile",)
    assert authenticator._options.scopes() == ("openid", "email", "profile")


# ---- start: the authorization request ----


async def test_start_redirects_to_the_authorization_endpoint() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    response = await _start(authenticator, _session())

    assert response.get_status_code() == 302
    location = urlsplit(_location(response))
    assert f"{location.scheme}://{location.netloc}{location.path}" == _AUTHORIZATION_ENDPOINT


async def test_start_sends_the_managed_parameters() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    params = _params_of(await _start(authenticator, _session()))

    assert params["response_type"] == "code"
    assert params["client_id"] == _CLIENT_ID
    assert params["redirect_uri"] == _CHECK_PATH
    assert params["scope"] == "openid"
    assert len(params["state"]) == 64
    assert int(params["state"], 16) >= 0  # hex-encoded random bytes
    assert len(params["nonce"]) == 43


async def test_start_stores_the_attempt_in_the_session() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    session = _session()

    params = _params_of(await _start(authenticator, session))

    attempt = await session.get(f"{_PREFIX}attempt.{params['state']}")
    assert isinstance(attempt, dict)
    assert attempt["nonce"] == params["nonce"]
    assert attempt["redirect_uri"] == _CHECK_PATH
    verifier = cast("str", attempt["code_verifier"])
    assert len(verifier) == 64


async def test_the_pkce_challenge_is_s256_of_the_verifier() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    session = _session()

    params = _params_of(await _start(authenticator, session))
    attempt = await session.get(f"{_PREFIX}attempt.{params['state']}")
    assert isinstance(attempt, dict)
    verifier = cast("str", attempt["code_verifier"])

    expected = urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert params["code_challenge"] == expected
    assert params["code_challenge_method"] == "S256"


async def test_pkce_disabled_sends_no_challenge() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient(), options={"pkce_enabled": False})

    params = _params_of(await _start(authenticator, _session()))

    assert "code_challenge" not in params
    assert "code_challenge_method" not in params


async def test_pkce_plain_challenge_equals_the_verifier() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        options={"pkce_method": "plain"},
    )
    session = _session()

    params = _params_of(await _start(authenticator, session))
    attempt = await session.get(f"{_PREFIX}attempt.{params['state']}")
    assert isinstance(attempt, dict)
    verifier = cast("str", attempt["code_verifier"])

    assert params["code_challenge"] == verifier


async def test_the_scopes_carry_openid_first_and_split_on_whitespace() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        options={"scope": ("email profile", "openid")},
    )

    params = _params_of(await _start(authenticator, _session()))

    assert params["scope"] == "openid email profile"


async def test_a_max_age_option_is_sent_as_text() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient(), options={"max_age": 3600})

    params = _params_of(await _start(authenticator, _session()))

    assert params["max_age"] == "3600"


async def test_extra_authorization_params_are_merged() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        authorization_params={"ui_locales": "fr"},
    )

    params = _params_of(await _start(authenticator, _session()))

    assert params["ui_locales"] == "fr"


async def test_the_authorization_request_event_carries_the_request_and_the_params() -> None:
    dispatcher = RecordingDispatcher()
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        authorization_params={"ui_locales": "fr"},
        dispatcher=dispatcher,
    )
    session = _session()
    request = _request(session)

    _ = await authenticator.start(request)

    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert isinstance(event, OidcAuthorizationRequestEvent)
    assert event.get_request() is request
    assert event.get_firewall_name() == "main"
    assert event.get_params() == {"ui_locales": "fr"}


async def test_a_listener_setting_an_extra_param_is_merged_into_the_request() -> None:
    def listener(event: object) -> None:
        assert isinstance(event, OidcAuthorizationRequestEvent)
        event.set_param("login_hint", "alice@example.com")

    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        dispatcher=_ListenerDispatcher(listener),
    )

    params = _params_of(await _start(authenticator, _session()))

    assert params["login_hint"] == "alice@example.com"


async def test_a_listener_setting_a_managed_param_is_refused() -> None:
    def listener(event: object) -> None:
        assert isinstance(event, OidcAuthorizationRequestEvent)
        event.set_param("nonce", "attacker")

    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        dispatcher=_ListenerDispatcher(listener),
    )

    with pytest.raises(InvalidArgumentError) as raised:
        _ = await _start(authenticator, _session())

    assert '"nonce"' in str(raised.value)


async def test_the_sixth_concurrent_attempt_drops_the_oldest() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    session = _session()

    states = [_params_of(await _start(authenticator, session))["state"] for _ in range(6)]

    assert await _states_of(session) == states[1:]
    assert await session.has(f"{_PREFIX}attempt.{states[0]}") is False
    assert await session.has(f"{_PREFIX}attempt.{states[5]}") is True


async def test_start_without_a_session_is_refused() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    with pytest.raises(MissingSessionError):
        _ = await authenticator.start(make_message())


async def test_a_missing_authorization_endpoint_leaves_no_attempt_behind() -> None:
    document = _document()
    del document["authorization_endpoint"]
    client = _ScriptedClient()
    provider = _Provider()
    authenticator = OidcLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        provider,
        client,
        _discovery(document),
        OidcIdToken(clock=MockClock(_FROZEN)),
        _CLIENT_ID,
        _Success(),
        _Failure(),
        clock=MockClock(_FROZEN),
    )
    session = _session()

    with pytest.raises(AuthenticationError):
        _ = await _start(authenticator, session)

    assert await _states_of(session) == []


# ---- start: the re-authentication ----


async def test_a_re_authentication_forces_prompt_login_and_hints_the_id_token() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    token = _BearerToken()
    token.set_attribute("oidc_id_token", "the-previous-id-token")

    params = _params_of(await authenticator.start_re_authentication(_request(_session()), token))

    assert params["prompt"] == "login"
    assert params["id_token_hint"] == "the-previous-id-token"  # noqa: S105 -- a parameter name, not a credential


async def test_a_re_authentication_without_an_id_token_sends_no_hint() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    params = _params_of(
        await authenticator.start_re_authentication(_request(_session()), NullToken()),
    )

    assert params["prompt"] == "login"
    assert "id_token_hint" not in params


async def test_a_re_authentication_with_a_non_string_id_token_sends_no_hint() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())
    token = _BearerToken()
    token.set_attribute("oidc_id_token", 42)

    params = _params_of(
        await authenticator.start_re_authentication(_request(_session()), token),
    )

    assert params["prompt"] == "login"
    assert "id_token_hint" not in params


async def test_forced_params_win_over_a_listener() -> None:
    def listener(event: object) -> None:
        assert isinstance(event, OidcAuthorizationRequestEvent)
        event.set_param("prompt", "none")

    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        dispatcher=_ListenerDispatcher(listener),
    )
    token = _BearerToken()
    token.set_attribute("oidc_id_token", "the-previous-id-token")

    params = _params_of(await authenticator.start_re_authentication(_request(_session()), token))

    assert params["prompt"] == "login"
    assert params["id_token_hint"] == "the-previous-id-token"  # noqa: S105 -- a parameter name, not a credential


# ---- start: the public client ----


async def test_a_public_client_cannot_disable_pkce() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(method="none"),
        options={"pkce_enabled": False},
        signature_verifier=_verifier(_key()),
    )

    with pytest.raises(InvalidArgumentError) as raised:
        _ = await _start(authenticator, _session())

    assert "PKCE cannot be disabled" in str(raised.value)


async def test_a_public_client_must_verify_the_id_token_signature() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient(method="none"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = await _start(authenticator, _session())

    assert "signature must be verified" in str(raised.value)


async def test_a_confidential_client_may_disable_pkce() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(),
        options={"pkce_enabled": False},
    )

    response = await _start(authenticator, _session())

    assert response.get_status_code() == 302


async def test_a_public_client_with_pkce_and_a_verifier_starts() -> None:
    authenticator, *_rest = _authenticator(
        _ScriptedClient(method="none"),
        signature_verifier=_verifier(_key()),
    )

    response = await _start(authenticator, _session())

    assert response.get_status_code() == 302


# ---- authenticate: the callback ----


async def test_a_callback_is_consumed_end_to_end() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, provider, *_rest = _authenticator(client)
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    assert client.exchanges[0][:2] == ("the-code", _CHECK_PATH)
    assert client.exchanges[0][2] is not None
    assert client.user_info_calls == ["at-1"]
    token_data = passport.get_attribute("oidc_token_data")
    assert isinstance(token_data, dict)
    assert token_data["access_token"] == "at-1"  # noqa: S105 -- a fixture token, not a credential
    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"
    assert provider.loaded == ["alice"]


async def test_a_posted_callback_is_read_from_the_body() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    response = await _start(authenticator, session)
    state = _params_of(response)["state"]
    attempt = await session.get(f"{_PREFIX}attempt.{state}")
    assert isinstance(attempt, dict)
    client.remember_nonce(cast("str", attempt["nonce"]))
    callback = _request(
        session,
        method="POST",
        parsed_body={"state": state, "code": "the-code"},
    )
    passport = await authenticator.authenticate(callback)

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_an_empty_state_is_refused() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(_request(_session(), query="code=the-code"))

    assert str(raised.value) == "Invalid OIDC state parameter."


async def test_an_unknown_state_fails_like_an_empty_session() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(_session(), query="state=unknown&code=the-code"),
        )

    assert str(raised.value) == "Invalid OIDC state parameter."


async def test_a_replayed_callback_fails_on_the_state() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    _passport, _state = await _login(authenticator, client, session)

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={_state}&code=the-code"),
        )

    assert str(raised.value) == "Invalid OIDC state parameter."


async def test_a_callback_for_the_second_attempt_walks_past_the_first() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    _ = _params_of(await _start(authenticator, session))
    response = await _start(authenticator, session)
    second = _params_of(response)["state"]
    attempt = await session.get(f"{_PREFIX}attempt.{second}")
    assert isinstance(attempt, dict)
    client.remember_nonce(cast("str", attempt["nonce"]))

    passport = await authenticator.authenticate(
        _request(session, query=f"state={second}&code=the-code"),
    )

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_a_corrupted_attempt_fails_like_an_unknown_state() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]
    await session.set(f"{_PREFIX}attempt.{state}", "not-a-mapping")

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={state}&code=the-code"),
        )

    assert str(raised.value) == "Invalid OIDC state parameter."


async def test_a_provider_error_names_its_description_and_spares_the_other_attempts() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)
    session = _session()

    first = _params_of(await _start(authenticator, session))["state"]
    second = _params_of(await _start(authenticator, session))["state"]

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(
                session,
                query=f"state={first}&error=access_denied&error_description=the+user+refused",
            ),
        )

    assert str(raised.value) == 'OIDC provider returned an error: "the user refused"'
    assert await _states_of(session) == [second]


async def test_a_provider_error_without_a_description_names_the_error() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={state}&error=access_denied"),
        )

    assert str(raised.value) == 'OIDC provider returned an error: "access_denied"'


async def test_a_missing_iss_is_refused_when_the_provider_announces_support() -> None:
    key = _key()
    client = _ScriptedClient(key)
    document = _document(authorization_response_iss_parameter_supported=True)
    provider = _Provider()
    authenticator = OidcLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        provider,
        client,
        _discovery(document),
        OidcIdToken(clock=MockClock(_FROZEN)),
        _CLIENT_ID,
        _Success(),
        _Failure(),
        clock=MockClock(_FROZEN),
    )
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert '"iss" authorization response parameter' in str(raised.value)


async def test_a_missing_iss_is_accepted_without_the_announcement() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_a_mismatched_iss_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(
            authenticator,
            client,
            session,
            extra_query="&iss=https://evil.example",
        )

    assert '"iss" parameter does not match the expected issuer' in str(raised.value)


async def test_a_matching_iss_is_accepted() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    passport, _state = await _login(
        authenticator,
        client,
        session,
        extra_query=f"&iss={_ISSUER}",
    )

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_a_missing_code_is_refused() -> None:
    client = _ScriptedClient()
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(_request(session, query=f"state={state}"))

    assert str(raised.value) == "Missing authorization code in OIDC callback."


async def test_a_missing_nonce_in_the_attempt_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]
    await session.set(
        f"{_PREFIX}attempt.{state}",
        {"code_verifier": "a-verifier", "redirect_uri": _CHECK_PATH},
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={state}&code=the-code"),
        )

    assert str(raised.value) == "Missing OIDC nonce in session."


async def test_a_missing_pkce_verifier_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]
    await session.set(
        f"{_PREFIX}attempt.{state}",
        {"nonce": "a-nonce", "redirect_uri": _CHECK_PATH},
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={state}&code=the-code"),
        )

    assert str(raised.value) == "Missing PKCE code verifier in session."


async def test_a_missing_redirect_uri_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    session = _session()

    state = _params_of(await _start(authenticator, session))["state"]
    await session.set(
        f"{_PREFIX}attempt.{state}",
        {"nonce": "a-nonce", "code_verifier": "a-verifier"},
    )

    with pytest.raises(AuthenticationError) as raised:
        _ = await authenticator.authenticate(
            _request(session, query=f"state={state}&code=the-code"),
        )

    assert str(raised.value) == "Missing OIDC redirect URI in session."


async def test_pkce_disabled_exchanges_without_a_verifier() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client, options={"pkce_enabled": False})
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"
    assert client.exchanges[0][2] is None


async def test_an_answer_without_an_id_token_is_refused() -> None:
    client = _ScriptedClient(answer={"token_type": "Bearer", "access_token": "at-1"})
    authenticator, *_rest = _authenticator(client)
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert '"id_token"' in str(raised.value)


async def test_an_answer_without_an_access_token_is_refused() -> None:
    client = _ScriptedClient(answer={"token_type": "Bearer", "id_token": "an-id-token"})
    authenticator, *_rest = _authenticator(client)
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert '"access_token"' in str(raised.value)


async def test_the_id_token_signature_is_verified_when_a_verifier_is_given() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client, signature_verifier=_verifier(key))
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    user = await passport.get_user()
    assert user.get_user_identifier() == "alice"


async def test_a_token_signed_by_another_key_is_refused_by_the_verifier() -> None:
    signing, announced = _key("k1"), _key("k2")
    client = _ScriptedClient(signing)
    authenticator, *_rest = _authenticator(client, signature_verifier=_verifier(announced))
    session = _session()

    with pytest.raises(AuthenticationError):
        _passport, _state = await _login(authenticator, client, session)


async def test_a_wrong_nonce_in_the_id_token_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"nonce": "another-nonce"})
    authenticator, *_rest = _authenticator(client)
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert "nonce" in str(raised.value)


async def test_the_user_info_sub_must_match_the_id_token() -> None:
    key = _key()
    client = _ScriptedClient(key, user_info={"sub": "bob"})
    authenticator, *_rest = _authenticator(client)
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert '"sub" claim from the UserInfo endpoint' in str(raised.value)


async def test_the_user_info_claims_are_the_badge_attributes() -> None:
    key = _key()
    client = _ScriptedClient(
        key,
        user_info={"sub": "alice", "email": "alice@example.com"},
    )
    authenticator, *_rest = _authenticator(client)
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    badge = passport.get_user_badge()
    assert badge.get_attributes()["email"] == "alice@example.com"


async def test_the_id_token_claims_are_the_user_source_when_configured() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"email": "alice@example.com"})
    authenticator, *_rest = _authenticator(
        client,
        options={"user_data_source": "id_token"},
    )
    session = _session()

    passport, _state = await _login(authenticator, client, session)

    assert client.user_info_calls == []
    badge = passport.get_user_badge()
    assert badge.get_attributes()["email"] == "alice@example.com"


async def test_a_missing_identifier_claim_is_refused() -> None:
    key = _key()
    client = _ScriptedClient(key, user_info={"sub": "alice"})
    authenticator, *_rest = _authenticator(
        client,
        options={"user_identifier_claim": "preferred_username"},
    )
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert '"preferred_username" claim is missing' in str(raised.value)


async def test_a_requested_max_age_is_checked_against_the_auth_time() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"auth_time": _NOW - 7200})
    authenticator, *_rest = _authenticator(client, options={"max_age": 3600})
    session = _session()

    with pytest.raises(AuthenticationError) as raised:
        _passport, _state = await _login(authenticator, client, session)

    assert "auth_time" in str(raised.value)


# ---- create_token: the attributes and the proofs ----


async def test_the_token_carries_the_oidc_attributes() -> None:
    key = _key()
    client = _ScriptedClient(
        key,
        extra={"refresh_token": "rt-1", "expires_in": 3600},
    )
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_attribute("oidc_id_token") == client.last_id_token
    assert token.get_attribute("oidc_access_token") == "at-1"
    assert token.get_attribute("oidc_refresh_token") == "rt-1"
    assert token.get_attribute("oidc_access_token_expires_at") == _NOW + 3600
    assert token.get_attribute("oidc_acr") is None
    assert token.get_attribute("oidc_sid") is None
    # No "auth_time" and no "amr" in the ID token: nothing to record a proof of.
    assert dict(token.get_authentication_proofs()) == {}


async def test_an_answer_without_expires_in_stores_no_expiry() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_attribute("oidc_refresh_token") is None
    assert token.get_attribute("oidc_access_token_expires_at") is None


async def test_an_auth_time_from_the_future_is_clamped_to_the_present() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"auth_time": _NOW + 3600})
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_authentication_proofs() == {
        AuthenticationMethod.UNSPECIFIED: _NOW,
    }


async def test_the_amr_methods_key_the_proofs() -> None:
    key = _key()
    client = _ScriptedClient(
        key,
        claims={"auth_time": _NOW - 60, "amr": ["pwd", "mfa", 42], "acr": "gold", "sid": "sess-1"},
    )
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_authentication_proofs() == {"pwd": _NOW - 60, "mfa": _NOW - 60}
    assert token.get_attribute("oidc_acr") == "gold"
    assert token.get_attribute("oidc_sid") == "sess-1"


async def test_without_auth_time_the_login_instant_is_the_proof() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"amr": ["pwd"]})
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_authentication_proofs() == {"pwd": _NOW}


async def test_without_amr_and_auth_time_no_proof_is_recorded() -> None:
    key = _key()
    client = _ScriptedClient(key)
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert dict(token.get_authentication_proofs()) == {}


async def test_an_empty_acr_or_sid_is_no_class_and_no_session() -> None:
    key = _key()
    client = _ScriptedClient(key, claims={"acr": "", "sid": ""})
    authenticator, *_rest = _authenticator(client)
    passport, _state = await _login(authenticator, client, _session())

    token = await authenticator.create_token(passport, "main")

    assert token.get_attribute("oidc_acr") is None
    assert token.get_attribute("oidc_sid") is None


async def test_a_passport_without_token_data_stamps_no_tokens() -> None:
    authenticator, provider, *_rest = _authenticator(_ScriptedClient())
    passport = SelfValidatingPassport(
        UserBadge("alice", user_loader=provider.load_user_by_identifier),
    )

    token = await authenticator.create_token(passport, "main")

    assert token.has_attribute("oidc_id_token") is False
    assert token.get_attribute("oidc_acr") is None
    assert token.get_attribute("oidc_sid") is None


# ---- the hooks ----


async def test_a_successful_login_clears_the_pending_attempts_and_delegates() -> None:
    client = _ScriptedClient()
    authenticator, _provider, success, _failure = _authenticator(client)
    session = _session()
    _ = _params_of(await _start(authenticator, session))
    _ = _params_of(await _start(authenticator, session))
    token = NullToken()

    response = await authenticator.on_authentication_success(
        _request(session),
        token,
        "main",
    )

    assert response is not None
    assert response.get_status_code() == 200
    assert success.tokens == [token]
    assert await _states_of(session) == []


async def test_a_failed_login_delegates_to_the_failure_handler() -> None:
    authenticator, *_provider, _success, failure = _authenticator(_ScriptedClient())
    error = AuthenticationError("refused")

    response = await authenticator.on_authentication_failure(_request(_session()), error)

    assert response is not None
    assert response.get_status_code() == 401
    assert failure.errors == [error]


def test_the_login_is_interactive() -> None:
    authenticator, *_rest = _authenticator(_ScriptedClient())

    assert authenticator.is_interactive() is True
