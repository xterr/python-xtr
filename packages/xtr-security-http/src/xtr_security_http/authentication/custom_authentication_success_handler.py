"""A success handler the application supplied, handed the options and the firewall's name."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, final, runtime_checkable

from typing_extensions import override

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
    """

    __slots__ = ("_firewall_name", "_handler", "_options")

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
        self._handler = handler
        self._options = dict(options)
        self._firewall_name = firewall_name

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface | None:
        """Hand the options and the firewall's name over, then let the handler answer."""
        if isinstance(self._handler, _OptionsAware):
            self._handler.set_options(self._options)
        if isinstance(self._handler, _FirewallNamed):
            self._handler.set_firewall_name(self._firewall_name)
        return await self._handler.on_authentication_success(request, token)
