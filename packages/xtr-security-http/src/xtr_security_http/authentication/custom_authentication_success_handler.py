"""A success handler the application supplied, handed the options and the firewall's name."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, Protocol, final, override, runtime_checkable

from .authentication_success_handler_interface import AuthenticationSuccessHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["CustomAuthenticationSuccessHandler"]


@runtime_checkable
class _OptionsAware(Protocol):
    """What a handler that takes options at call time looks like."""

    def set_options(self, options: Mapping[str, object]) -> None:
        """Record ``options`` for the next answer."""
        ...


@runtime_checkable
class _FirewallNamed(Protocol):
    """What a handler that takes its firewall's name at call time looks like."""

    def set_firewall_name(self, firewall_name: str) -> None:
        """Record ``firewall_name`` for the next answer."""
        ...


@final
class CustomAuthenticationSuccessHandler(AuthenticationSuccessHandlerInterface):
    """Delegates a success answer to the application's own handler, options first.

    The wiring knows the firewall's options and its name — where to return
    the caller to, which firewall authenticated them — while the application
    knows what the answer should look like. This is the seam between them:
    both are handed to the handler when they can be (a handler that takes
    them), and the answer is the handler's own either way.

    The wrapper configures a copy of the handler of its own, once, so two
    firewalls sharing one handler never answer with each other's options.
    The copy is shallow: a handler's ``set_options`` and
    ``set_firewall_name`` must rebind what they set, not change state the
    copies share.
    """

    __slots__ = ("_handler",)

    def __init__(
        self,
        handler: AuthenticationSuccessHandlerInterface,
        options: Mapping[str, object],
        firewall_name: str,
    ) -> None:
        """Record the application's handler, the options and the firewall's name.

        Args:
            handler: The application's own success handler, asked last.
            options: The options the wiring collected for the firewall, for
                a handler that takes them.
            firewall_name: The firewall that authenticated, for a handler
                that keys its answers by one.
        """
        own = copy(handler)
        if isinstance(own, _OptionsAware):
            own.set_options(dict(options))
        if isinstance(own, _FirewallNamed):
            own.set_firewall_name(firewall_name)
        self._handler = own

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        """Let the configured copy of the handler answer."""
        return await self._handler.on_authentication_success(request, token)
