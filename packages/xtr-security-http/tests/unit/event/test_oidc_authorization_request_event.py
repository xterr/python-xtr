"""The event dispatched before the caller is sent to the OIDC authorization endpoint."""

from __future__ import annotations

from tests.support.messages import make_message
from xtr_security_http.event.oidc_authorization_request_event import (
    OidcAuthorizationRequestEvent,
)


def test_the_event_carries_the_request_the_firewall_and_the_params() -> None:
    request = make_message()

    event = OidcAuthorizationRequestEvent(request, "main", {"ui_locales": "fr"})

    assert event.get_request() is request
    assert event.get_firewall_name() == "main"
    assert event.get_params() == {"ui_locales": "fr"}


def test_the_params_are_returned_as_a_copy() -> None:
    event = OidcAuthorizationRequestEvent(make_message(), "main", {"ui_locales": "fr"})

    params = event.get_params()
    event.set_param("prompt", "none")

    assert params == {"ui_locales": "fr"}


def test_set_param_adds_one_parameter() -> None:
    event = OidcAuthorizationRequestEvent(make_message(), "main", {"ui_locales": "fr"})

    event.set_param("login_hint", "alice@example.com")

    assert event.get_params() == {"ui_locales": "fr", "login_hint": "alice@example.com"}


def test_remove_param_drops_one_parameter() -> None:
    event = OidcAuthorizationRequestEvent(make_message(), "main", {"ui_locales": "fr"})

    event.remove_param("ui_locales")

    assert event.get_params() == {}


def test_remove_param_leaves_an_absent_one_alone() -> None:
    event = OidcAuthorizationRequestEvent(make_message(), "main", {})

    event.remove_param("ui_locales")

    assert event.get_params() == {}


def test_set_params_replaces_the_whole_list() -> None:
    event = OidcAuthorizationRequestEvent(make_message(), "main", {"ui_locales": "fr"})

    event.set_params({"prompt": "none"})

    assert event.get_params() == {"prompt": "none"}


def test_the_params_are_copied_at_construction() -> None:
    given: dict[str, str] = {"ui_locales": "fr"}
    event = OidcAuthorizationRequestEvent(make_message(), "main", given)

    given["prompt"] = "none"

    assert event.get_params() == {"ui_locales": "fr"}
