"""The prompt step, built by hand, decides a sign-in's ``prompt`` and ``max_age``.

The authorization server is a real one over in-memory storage, so the request
the step reads is validated as the authorization endpoint validates it. No
firewall runs: the token the chain would have restored is put in the storage
directly, and no session is parked, as on a firewall that keeps none.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlsplit

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import ServerRequest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.http_utils import HttpUtils
from xtr_security_oauth2_server.entity import Client
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.repositories import (
    InMemoryAccessTokenRepository,
    InMemoryAuthCodeRepository,
    InMemoryClientRepository,
    InMemoryRefreshTokenRepository,
    InMemoryScopeRepository,
)
from tests.support.signing import FROZEN_NOW, make_clock, make_signer
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_openid_connect_server.firewall.open_id_prompt_listener import (
    OpenIdPromptListener,
)
from xtr_security_openid_connect_server.grant.open_id_auth_code_grant import OpenIdAuthCodeGrant

if TYPE_CHECKING:
    from xtr_clock import MockClock
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio

_REDIRECT_URI = "https://client.test/callback"
_NOW = int(FROZEN_NOW.timestamp())


def _server(clock: MockClock) -> AuthorizationServer:
    clients = InMemoryClientRepository()
    client = Client()
    client.set_identifier("my-client")
    client.set_name("my-client")
    client.set_redirect_uri([_REDIRECT_URI])
    client.set_confidential(True)
    clients.add(client, "s3cret")
    server = AuthorizationServer(
        clients,
        InMemoryAccessTokenRepository(),
        InMemoryScopeRepository("openid"),
        make_signer("RS256", clock=clock),
        ENCRYPTION_KEY,
        "key",
        EventDispatcher(),
        None,
    )
    server.enable_grant_type(
        OpenIdAuthCodeGrant(
            EventDispatcher(),
            clock,
            InMemoryAuthCodeRepository(),
            InMemoryRefreshTokenRepository(),
            timedelta(minutes=10),
            timedelta(days=7),
            False,
        ),
    )
    return server


def _signed_in(*proofs: int) -> TokenInterface:
    token = PostAuthenticationToken(
        InMemoryUser("alice", roles=["ROLE_USER"]), "main", ["ROLE_USER"]
    )
    token.set_authentication_proofs({f"method-{index}": at for index, at in enumerate(proofs)})
    return token


def _listener(token: TokenInterface | None = None) -> OpenIdPromptListener:
    clock = make_clock()
    storage = TokenStorage()
    storage.set_token(token)
    return OpenIdPromptListener(
        storage,
        _server(clock),
        HttpUtils(ResponseFactory()),
        ResponseFactory(),
        StarletteHttpFactory(),
        login_path="/login",
        login_firewall="main",
        authorize_path="/authorize",
        clock=clock,
    )


def _authorize(path: str = "/authorize", **extra: str) -> ServerRequestInterface:
    query = {
        "response_type": "code",
        "client_id": "my-client",
        "redirect_uri": _REDIRECT_URI,
        "scope": "openid",
        "state": "xyz",
        **extra,
    }
    return ServerRequest("GET", f"{path}?{urlencode(query)}").with_query_params(query)


async def _decided(listener: OpenIdPromptListener, **extra: str) -> RequestEvent:
    event = RequestEvent(_authorize(**extra), {})
    await listener.authenticate(event)
    return event


def _location_query(event: RequestEvent) -> dict[str, str]:
    assert event.response is not None
    assert event.response.status_code == 302
    return dict(parse_qsl(urlsplit(event.response.headers["location"]).query))


async def test_it_runs_on_the_authorization_endpoint() -> None:
    assert await _listener().supports(_authorize()) is True


async def test_it_leaves_every_other_path_alone() -> None:
    assert await _listener().supports(_authorize("/token")) is False


def test_it_runs_after_the_token_is_known_and_before_access_control() -> None:
    assert OpenIdPromptListener.get_priority() == -200


async def test_a_request_asking_nothing_of_the_sign_in_is_left_to_the_endpoint() -> None:
    event = await _decided(_listener())

    assert event.response is None


async def test_prompt_none_with_nobody_signed_in_is_answered_with_login_required() -> None:
    event = await _decided(_listener(), prompt="none")

    sent = _location_query(event)
    assert (sent["error"], sent["state"]) == ("login_required", "xyz")


async def test_prompt_none_with_the_end_user_signed_in_goes_on() -> None:
    event = await _decided(_listener(_signed_in(_NOW)), prompt="none")

    assert event.response is None


async def test_a_sign_in_within_max_age_goes_on() -> None:
    event = await _decided(_listener(_signed_in(_NOW - 60)), max_age="60")

    assert event.response is None


async def test_the_newest_proof_is_the_sign_in_max_age_measures() -> None:
    event = await _decided(
        _listener(_signed_in(_NOW - 3600, _NOW - 10)), prompt="none", max_age="60"
    )

    assert event.response is None


async def test_a_sign_in_proving_nothing_is_too_old_for_any_max_age() -> None:
    event = await _decided(_listener(_signed_in()), prompt="none", max_age="3600")

    assert _location_query(event)["error"] == "login_required"


async def test_a_sign_in_older_than_max_age_is_too_old_for_prompt_none() -> None:
    event = await _decided(_listener(_signed_in(_NOW - 61)), prompt="none", max_age="60")

    assert _location_query(event)["error"] == "login_required"


async def test_a_refused_request_is_answered_as_the_endpoint_answers_it() -> None:
    event = await _decided(_listener(), prompt="none", redirect_uri="https://attacker.test/")

    assert event.response is not None
    assert "location" not in event.response.headers
    assert event.response.status_code in {400, 401}


async def test_a_re_login_with_no_session_to_return_to_names_the_stateless_firewall() -> None:
    with pytest.raises(InvalidConfigurationError, match="stateless") as raised:
        _ = await _decided(_listener(_signed_in(_NOW)), prompt="login")

    assert '"main"' in str(raised.value)


def test_it_is_described_by_its_type_alone() -> None:
    assert repr(_listener()) == "OpenIdPromptListener()"
