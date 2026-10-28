"""A user-supplied success handler, handed the wiring's options and the firewall's name."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken

from tests.support.messages import make_message
from xtr_security_http.authentication.custom_authentication_success_handler import (
    CustomAuthenticationSuccessHandler,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

pytestmark = pytest.mark.anyio


@final
class _OptionsTaking:
    """A handler that takes its options and its firewall's name at call time."""

    def __init__(self) -> None:
        self.options: dict[str, object] | None = None
        self.firewall_name: str | None = None
        self.tokens: list[TokenInterface] = []

    def set_options(self, options: dict[str, object]) -> None:
        """Record the options the wiring handed."""
        self.options = dict(options)

    def set_firewall_name(self, firewall_name: str) -> None:
        """Record the firewall whose login this handler answers."""
        self.firewall_name = firewall_name

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        """Record the token, and answer with a response of the handler's own."""
        del request
        self.tokens.append(token)
        return ResponseFactory().create_response(418)


@final
class _Plain:
    """A handler that answers, taking neither options nor a firewall's name."""

    def __init__(self) -> None:
        self.tokens: list[TokenInterface] = []

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        """Record the token, and answer with a response of the handler's own."""
        del request
        self.tokens.append(token)
        return ResponseFactory().create_response(418)


async def test_the_options_and_the_firewalls_name_are_handed_to_a_handler_that_takes_them() -> None:
    handler = _OptionsTaking()
    token = NullToken()
    wrapper = CustomAuthenticationSuccessHandler(handler, {"default_target_path": "/home"}, "api")

    response = await wrapper.on_authentication_success(make_message(), token)

    assert handler.options == {"default_target_path": "/home"}
    assert handler.firewall_name == "api"
    assert handler.tokens == [token]
    assert response is not None
    assert response.get_status_code() == 418


async def test_a_handler_without_the_duck_typed_setters_is_asked_without_them() -> None:
    handler = _Plain()
    token = NullToken()
    wrapper = CustomAuthenticationSuccessHandler(handler, {"default_target_path": "/home"}, "api")

    response = await wrapper.on_authentication_success(make_message(), token)

    assert handler.tokens == [token]
    assert response is not None
    assert response.get_status_code() == 418
