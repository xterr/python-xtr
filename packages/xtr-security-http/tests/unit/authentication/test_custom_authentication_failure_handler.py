"""A user-supplied failure handler, handed the wiring's options."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import AuthenticationError, BadCredentialsError

from tests.support.messages import make_message
from xtr_security_http.authentication.custom_authentication_failure_handler import (
    CustomAuthenticationFailureHandler,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

pytestmark = pytest.mark.anyio


@final
class _OptionsTaking:
    """A handler that takes its options at call time, and records the ask."""

    def __init__(self) -> None:
        self.options: dict[str, object] | None = None
        self.failures: list[AuthenticationError] = []

    def set_options(self, options: dict[str, object]) -> None:
        """Record the options the wiring handed."""
        self.options = dict(options)

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Record the failure, and answer with a response of the handler's own."""
        del request
        self.failures.append(error)
        return ResponseFactory().create_response(418)


@final
class _Plain:
    """A handler that answers, taking no options."""

    def __init__(self) -> None:
        self.failures: list[AuthenticationError] = []

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Record the failure, and answer with a response of the handler's own."""
        del request
        self.failures.append(error)
        return ResponseFactory().create_response(418)


async def test_the_options_are_handed_to_a_handler_that_takes_them() -> None:
    handler = _OptionsTaking()
    error = BadCredentialsError("failed")
    wrapper = CustomAuthenticationFailureHandler(handler, {"login_path": "/sign-in"})

    response = await wrapper.on_authentication_failure(make_message(), error)

    assert handler.options == {"login_path": "/sign-in"}
    assert handler.failures == [error]
    assert response.get_status_code() == 418


async def test_a_handler_without_set_options_is_asked_without_them() -> None:
    handler = _Plain()
    error = BadCredentialsError("failed")
    wrapper = CustomAuthenticationFailureHandler(handler, {"login_path": "/sign-in"})

    response = await wrapper.on_authentication_failure(make_message(), error)

    assert handler.failures == [error]
    assert response.get_status_code() == 418
