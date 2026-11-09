"""Reading the prompt a sign-in is asked with, and the refusals it can end in."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from xtr_http_message import Response
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
    AuthorizationRequestResolveEvent,
)
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from xtr_security_openid_connect_server.prompt import consent_required, login_required, parse_prompt
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)

_CALLBACK = "https://client.test/callback"


def _event(
    redirect_uri: str | None = _CALLBACK,
    state: str | None = "xyz",
) -> AuthorizationRequestResolveEvent:
    """Return the question a consent listener is asked about a silent sign-in."""
    request = OpenIdAuthorizationRequest()
    request.set_grant_type_id("authorization_code")
    request.set_redirect_uri(redirect_uri)
    if state is not None:
        request.set_state(state)
    request.set_prompt(frozenset({"none"}))

    return AuthorizationRequestResolveEvent(
        request,
        (Scope("openid"),),
        Client("My client", "my-client", None),
        InMemoryUser("alice"),
    )


def test_a_request_with_no_prompt_asks_for_nothing() -> None:
    assert parse_prompt(None) == frozenset()


def test_an_empty_prompt_asks_for_nothing() -> None:
    assert parse_prompt("") == frozenset()


@pytest.mark.parametrize("value", ["none", "login", "consent"])
def test_it_reads_each_value_this_server_acts_on(value: str) -> None:
    assert parse_prompt(value) == frozenset({value})


def test_it_reads_login_and_consent_together() -> None:
    assert parse_prompt("login consent") == frozenset({"login", "consent"})


def test_a_repeated_or_padded_value_is_read_once() -> None:
    assert parse_prompt(" login  login ") == frozenset({"login"})


def test_none_combined_with_another_value_is_refused() -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = parse_prompt("none login")

    assert raised.value.get_error_type() == "invalid_request"


@pytest.mark.parametrize(
    "prompt",
    [
        # Defined for account choosers, which this server does not run; taking
        # it silently would answer as though the end-user had chosen.
        "select_account",
        # The values are case sensitive.
        "Login",
        "login consent relogin",
        # They are separated by spaces, and by nothing else.
        "login\tconsent",
    ],
)
def test_a_value_this_server_does_not_act_on_is_refused(prompt: str) -> None:
    with pytest.raises(OAuthServerError) as raised:
        _ = parse_prompt(prompt)

    assert raised.value.get_error_type() == "invalid_request"


def test_a_refusal_does_not_repeat_the_value_back() -> None:
    # The answer may end up in a page a client renders; it names the parameter,
    # never what the request put in it.
    with pytest.raises(OAuthServerError) as raised:
        _ = parse_prompt("<script>")

    assert all("<script>" not in value for value in raised.value.get_payload().values())


@pytest.mark.parametrize(
    ("error", "error_type", "code"),
    [
        (consent_required(_event()), "consent_required", 16),
        (login_required(_CALLBACK, "xyz"), "login_required", 17),
    ],
)
def test_each_refusal_is_catalogued_under_a_number_of_its_own(
    error: OAuthServerError,
    error_type: str,
    code: int,
) -> None:
    assert error.get_error_type() == error_type
    assert error.get_code() == code
    assert error.get_http_status_code() == 400


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "error_type"),
    [
        (consent_required(_event()), "consent_required"),
        (login_required(_CALLBACK, "xyz"), "login_required"),
    ],
)
async def test_a_refusal_is_delivered_to_the_redirect_uri_carrying_the_state(
    error: OAuthServerError,
    error_type: str,
) -> None:
    answer = await error.generate_http_response(Response())

    location = answer.get_header_line("location")
    query = parse_qs(urlsplit(location).query)
    assert answer.get_status_code() == 302
    assert location.startswith(f"{_CALLBACK}?")
    assert query["error"] == [error_type]
    assert query["state"] == ["xyz"]


@pytest.mark.parametrize(
    "error",
    [consent_required(_event(state=None)), login_required(_CALLBACK, None)],
)
def test_a_refusal_carries_no_state_the_request_did_not(error: OAuthServerError) -> None:
    assert error.get_redirect_uri() == _CALLBACK


@pytest.mark.parametrize(
    "error",
    [consent_required(_event(redirect_uri=None)), login_required(None, "xyz")],
)
def test_a_refusal_with_no_redirect_uri_to_go_to_is_answered_as_a_document(
    error: OAuthServerError,
) -> None:
    assert error.has_redirect() is False
