"""A failure handler the application supplied, handed the options the wiring collected."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, final, runtime_checkable

from typing_extensions import override

from .authentication_failure_handler_interface import AuthenticationFailureHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["CustomAuthenticationFailureHandler"]


@runtime_checkable
class _OptionsAware(Protocol):
    """What a handler that takes options at call time looks like."""

    def set_options(self, options: Mapping[str, object]) -> None:
        """Record ``options`` for the next answer."""
        ...


@final
class CustomAuthenticationFailureHandler(AuthenticationFailureHandlerInterface):
    """Delegates a failure answer to the application's own handler, options first.

    The wiring knows the firewall's options — where its login page is, which
    parameter carries a failure path — while the application knows what the
    answer should look like. This is the seam between them: the options are
    handed to the handler when they can be (a handler that takes them), and
    the answer is the handler's own either way.
    """

    __slots__ = ("_handler", "_options")

    def __init__(
        self,
        handler: AuthenticationFailureHandlerInterface,
        options: Mapping[str, object],
    ) -> None:
        """Record the application's handler and the options to hand it.

        Args:
            handler: The application's own failure handler, asked last.
            options: The options the wiring collected for the firewall, for
                a handler that takes them.
        """
        self._handler = handler
        self._options = dict(options)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Hand the options over, then let the application's handler answer."""
        if isinstance(self._handler, _OptionsAware):
            self._handler.set_options(self._options)
        return await self._handler.on_authentication_failure(request, error)
