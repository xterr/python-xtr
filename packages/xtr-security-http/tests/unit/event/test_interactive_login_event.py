"""The interactive-login event carries the request and the token, replacing neither."""

from __future__ import annotations

import inspect

from xtr_security_core.authentication.token.null_token import NullToken

from tests.support.messages import make_message
from xtr_security_http.event.interactive_login_event import InteractiveLoginEvent


def test_it_carries_the_request_and_the_token() -> None:
    request = make_message()
    token = NullToken()

    event = InteractiveLoginEvent(request, token)

    assert event.get_request() is request
    assert event.get_authenticated_token() is token


def test_the_constructor_signature_is_aligned_with_the_upstream_order() -> None:
    names = list(inspect.signature(InteractiveLoginEvent.__init__).parameters)

    assert names == ["self", "request", "token"]


def test_a_listener_cannot_replace_the_token() -> None:
    # Upstream exposes no setter either: the announcement is read-only, and
    # the token it names is already the one the storage holds.
    assert not hasattr(InteractiveLoginEvent, "set_authenticated_token")
