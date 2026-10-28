"""The bare answers an exception listener falls back to, and how one is set.

The exception listener's own answers — the challenge a firewall with no
entry point gives, the refusal a denial ends in — and the one rule every
answer passes through on its way to the event: a response that already is
what the framework sends is set as it is, a pure message is converted
through the bridge first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)

from xtr_security_http._challenge import json_challenge

if TYPE_CHECKING:
    from xtr_http_kernel import ExceptionEvent
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["ExceptionAnswers"]


@final
class ExceptionAnswers:
    """Builds the bare ``401``/``403`` answers and sets a listener's answer on the event.

    The listener names no response class of its own: the bare answers are
    built through the response factory, so the challenge and the refusal
    carry the headers the framework's own answers do. A response that already
    is what the framework sends — the kernel's own dual response, a message
    and a framework response at once — is set on the event as it is; a pure
    message is converted through the bridge first, which is the kernel's rule
    for messages from elsewhere.
    """

    __slots__ = ("_bridge", "_responses")

    def __init__(
        self,
        responses: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
    ) -> None:
        """Record the response factory and the bridge.

        Args:
            responses: Builds the bare answers, so the class names no
                response class.
            bridge: Turns a handler's pure message response into one the
                lifecycle's event accepts.
        """
        self._responses = responses
        self._bridge = bridge

    async def bare_challenge(self) -> ResponseInterface:
        """Return a plain ``401`` carrying a bare bearer challenge."""
        return await json_challenge(
            self._responses,
            401,
            {"error": "unauthorized"},
            {"WWW-Authenticate": "Bearer"},
        )

    async def forbidden(self) -> ResponseInterface:
        """Return a plain, uncached ``403`` refusing the request."""
        return await json_challenge(
            self._responses,
            403,
            {"error": "access_denied"},
            {},
        )

    async def set_on(self, event: ExceptionEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``event`` as what the lifecycle can send.

        The kernel's own response is both a message and what the framework
        sends, so it is set as it is; a pure message — a handler built through
        another factory, a test's own — is converted through the bridge, the
        kernel's rule for messages from elsewhere.
        """
        if isinstance(response, FrameworkResponse):
            event.set_response(response)
            return
        event.set_response(await self._bridge.create_response(response))
