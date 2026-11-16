"""A failure handler the application supplied, handed the options the wiring collected."""

from __future__ import annotations

from copy import copy
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

    The wrapper configures a copy of the handler of its own, once, so two
    firewalls sharing one handler never answer with each other's options.
    The copy is shallow: a handler's ``set_options`` must rebind what it
    sets, not change state the copies share.
    """

    __slots__ = ("_handler",)

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
        own = copy(handler)
        if isinstance(own, _OptionsAware):
            own.set_options(dict(options))
        self._handler = own

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Let the configured copy of the application's handler answer."""
        return await self._handler.on_authentication_failure(request, error)
