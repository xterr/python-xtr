"""Redirecting a logout to the provider that issued the login."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from xtr_cache import ArrayAdapter
from xtr_clock import MockClock
from xtr_http_client import MockHttpClient
from xtr_http_client.response import MockResponse
from xtr_http_kernel.bridge import ResponseFactory
from xtr_http_message import HttpFactory
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.event_listener.default_logout_listener import DefaultLogoutListener
from xtr_security_http.event_listener.oidc_end_session_listener import OidcEndSessionListener
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio

_ISSUER = "https://issuer.example"
_DOCUMENT_URI = "https://issuer.example/.well-known/openid-configuration"
_END_SESSION_ENDPOINT = "https://issuer.example/end-session"
_ID_TOKEN = "header.payload.signature"  # noqa: S105 -- test material, not a credential


def _discovery(*, announces_endpoint: bool = True) -> OidcDiscovery:
    """A discovery reader over the test issuer, announcing what it is asked to."""
    document: dict[str, object] = {"issuer": _ISSUER}
    if announces_endpoint:
        document["end_session_endpoint"] = _END_SESSION_ENDPOINT
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps(document).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    return OidcDiscovery(client, ArrayAdapter(clock=MockClock()), issuer=_ISSUER)


def _listener_with_endpoint(endpoint: str) -> OidcEndSessionListener:
    """A listener whose provider announces ``endpoint`` as its end-session one."""
    client = MockHttpClient(
        [
            MockResponse(
                json.dumps({"issuer": _ISSUER, "end_session_endpoint": endpoint}).encode(),
                {"http_code": 200, "response_headers": {"Content-Type": "application/json"}},
            ),
        ],
        base_uri=_ISSUER,
    )
    return OidcEndSessionListener(
        OidcDiscovery(client, ArrayAdapter(clock=MockClock()), issuer=_ISSUER),
        HttpUtils(ResponseFactory()),
    )


def _token(**attributes: object) -> PostAuthenticationToken:
    token = PostAuthenticationToken(
        InMemoryUser("alice", roles=["ROLE_USER"]),
        "main",
        ["ROLE_USER"],
    )
    for name, value in attributes.items():
        token.set_attribute(name, value)
    return token


def _listener(
    *,
    announces_endpoint: bool = True,
    post_logout_redirect_path: str | None = None,
    logger: RecordingLogger | None = None,
) -> OidcEndSessionListener:
    return OidcEndSessionListener(
        _discovery(announces_endpoint=announces_endpoint),
        HttpUtils(ResponseFactory()),
        post_logout_redirect_path,
        logger,
    )


def _event(
    token: TokenInterface | None = None,
    response: ResponseInterface | None = None,
) -> LogoutEvent:
    """A logout event over ``token``, answered with ``response`` when one is given."""
    event = LogoutEvent(make_message(), token)
    if response is not None:
        event.set_response(response)
    return event


def test_it_subscribes_ahead_of_the_default_logout_listener() -> None:
    subscribed = OidcEndSessionListener.get_subscribed_events()
    assert subscribed == {LogoutEvent: ("on_logout", 65)}

    # The priority is what orders the two: this listener runs before the default's 64.
    mine = subscribed[LogoutEvent]
    default = DefaultLogoutListener.get_subscribed_events()[LogoutEvent]
    assert isinstance(mine, tuple)
    assert isinstance(default, tuple)
    assert mine[1] > default[1]


async def test_a_logout_with_an_id_token_redirects_to_the_end_session_endpoint() -> None:
    event = _event(_token(oidc_id_token=_ID_TOKEN))

    await _listener().on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_status_code() == 302
    assert response.get_header_line("location") == (
        f"{_END_SESSION_ENDPOINT}?id_token_hint={_ID_TOKEN}"
    )


async def test_the_hint_is_percent_encoded_per_rfc_3986() -> None:
    event = _event(_token(oidc_id_token="a b+c"))  # noqa: S106 -- test material, not a credential

    await _listener().on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_header_line("location").endswith("id_token_hint=a%20b%2Bc")


async def test_an_endpoint_already_carrying_a_query_is_joined_with_an_ampersand() -> None:
    event = _event(_token(oidc_id_token=_ID_TOKEN))

    await _listener_with_endpoint(f"{_END_SESSION_ENDPOINT}?tenant=shop").on_logout(event)

    response = event.get_response()
    assert response is not None
    assert response.get_header_line("location") == (
        f"{_END_SESSION_ENDPOINT}?tenant=shop&id_token_hint={_ID_TOKEN}"
    )


async def test_the_post_logout_redirect_is_carried_when_configured() -> None:
    event = _event(_token(oidc_id_token=_ID_TOKEN))

    await _listener(post_logout_redirect_path="/farewell").on_logout(event)

    response = event.get_response()
    assert response is not None
    assert "post_logout_redirect_uri=%2Ffarewell" in response.get_header_line("location")


async def test_no_post_logout_redirect_is_carried_by_default() -> None:
    event = _event(_token(oidc_id_token=_ID_TOKEN))

    await _listener().on_logout(event)

    response = event.get_response()
    assert response is not None
    assert "post_logout_redirect_uri" not in response.get_header_line("location")


async def test_a_logout_a_listener_answered_first_is_left_alone() -> None:
    answered = HttpFactory().create_response(200)
    event = _event(_token(oidc_id_token=_ID_TOKEN), answered)

    await _listener().on_logout(event)

    assert event.get_response() is answered


async def test_a_logout_without_a_token_is_left_alone() -> None:
    event = _event()

    await _listener().on_logout(event)

    assert event.get_response() is None


async def test_a_token_without_an_id_token_is_left_alone() -> None:
    event = _event(_token())

    await _listener().on_logout(event)

    assert event.get_response() is None


async def test_a_token_with_a_non_string_id_token_is_left_alone() -> None:
    event = _event(_token(oidc_id_token=7))

    await _listener().on_logout(event)

    assert event.get_response() is None


async def test_a_provider_announcing_no_endpoint_falls_back_to_a_local_logout() -> None:
    logger = RecordingLogger()
    event = _event(_token(oidc_id_token=_ID_TOKEN))

    await _listener(announces_endpoint=False, logger=logger).on_logout(event)

    assert event.get_response() is None
    assert logger.messages("warning") == [
        (
            'The OIDC provider does not announce a usable "end_session_endpoint"; '
            "falling back to a local logout."
        ),
    ]
