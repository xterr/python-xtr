"""A user-supplied failure handler, handed the wiring's options."""

from __future__ import annotations

import asyncio
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
    """A handler that takes its options, recording what it answered with.

    The record and the gate are shared by every copy a wrapper makes, so a
    test sees every answer; a gate, when set, holds each answer until it opens.
    """

    def __init__(self, gate: asyncio.Event | None = None) -> None:
        self.options: dict[str, object] | None = None
        self.answered: list[tuple[dict[str, object] | None, AuthenticationError]] = []
        self.gate = gate

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
        if self.gate is not None:
            _ = await self.gate.wait()
        self.answered.append((self.options, error))
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

    assert handler.answered == [({"login_path": "/sign-in"}, error)]
    assert response.get_status_code() == 418


async def test_two_firewalls_sharing_a_handler_keep_their_own_options() -> None:
    gate = asyncio.Event()
    handler = _OptionsTaking(gate)
    error = BadCredentialsError("failed")
    main = CustomAuthenticationFailureHandler(handler, {"login_path": "/main"})
    admin = CustomAuthenticationFailureHandler(handler, {"login_path": "/admin"})

    first = asyncio.create_task(main.on_authentication_failure(make_message(), error))
    await asyncio.sleep(0)
    second = asyncio.create_task(admin.on_authentication_failure(make_message(), error))
    await asyncio.sleep(0)
    gate.set()
    _ = await asyncio.gather(first, second)

    assert sorted(str(options) for options, _error in handler.answered) == [
        "{'login_path': '/admin'}",
        "{'login_path': '/main'}",
    ]


async def test_a_handler_without_set_options_is_asked_without_them() -> None:
    handler = _Plain()
    error = BadCredentialsError("failed")
    wrapper = CustomAuthenticationFailureHandler(handler, {"login_path": "/sign-in"})

    response = await wrapper.on_authentication_failure(make_message(), error)

    assert handler.failures == [error]
    assert response.get_status_code() == 418
