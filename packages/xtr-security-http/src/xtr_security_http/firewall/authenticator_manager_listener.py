"""The chain's authentication step: the manager, asked over the request's carrier."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .abstract_listener import AbstractListener

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.authentication.authenticator_manager_interface import (
        AuthenticatorManagerInterface,
    )

__all__ = ["AuthenticatorManagerListener"]


@final
class AuthenticatorManagerListener(AbstractListener):
    """Runs a firewall's authenticators over the request, as a chain step.

    A thin delegation: the manager's supports pass answers ``supports``, and
    the pass that authenticates answers the request — a response it produced
    is set on the event, which is also what stops the chain. The listener
    decides nothing of its own; skipping it when no authenticator applies is
    the chain's job, driven by the answer the manager gave.

    The manager's two passes hand each other what they learned through the
    request's security state, which rides the event's bag. ``authenticate``
    reads it off the event; ``supports`` is asked about the request alone,
    so the caller running the chain parks that bag on the request it asks
    about — the one place both hooks reach the same carrier.

    A response the manager produced is a message; the event answers with
    what the framework sends, so a pure message is converted through the
    bridge — the kernel's rule for messages from elsewhere — while the
    kernel's own dual response is set as it is.
    """

    __slots__ = ("_authenticator_manager", "_bridge")

    def __init__(
        self,
        authenticator_manager: AuthenticatorManagerInterface,
        bridge: StarletteHttpFactoryInterface,
    ) -> None:
        """Build the chain step over the firewall's manager and the bridge.

        Args:
            authenticator_manager: Drives the firewall's authenticators over
                the request.
            bridge: Turns a handler's pure message response into one the
                event accepts.
        """
        self._authenticator_manager = authenticator_manager
        self._bridge = bridge

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer whether any of the firewall's authenticators applies."""
        return self._authenticator_manager.supports(
            request, security_state_of(state_bag_of(request))
        )

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Authenticate the request, answering it when a handler produced a response.

        The request handed to the manager carries the event's bag, parked the
        way :meth:`supports` sees it, so the re-check, the authenticator and
        the success and failure hooks all reach the same carrier — a hook
        reading the bag off the request finds it in the live chain too.
        """
        asked = request_event.request.with_attribute(
            SecurityRequestAttributes.STATE_BAG, request_event.state
        )
        response = await self._authenticator_manager.authenticate_request(
            asked, security_state_of(request_event.state)
        )
        if response is None:
            return
        await self._answer(request_event, response)

    async def _answer(self, request_event: RequestEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``request_event`` as what the lifecycle can send."""
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))
