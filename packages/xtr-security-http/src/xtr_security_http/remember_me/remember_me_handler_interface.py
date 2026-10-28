"""What creates, checks and clears a remember-me cookie answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from .remember_me_details import RememberMeDetails

__all__ = ["RememberMeHandlerInterface"]


@runtime_checkable
class RememberMeHandlerInterface(Protocol):
    """Keeps the remember-me cookie of the request being handled.

    A handler is the one voice on what the cookie holds: it writes the cookie
    a login asks for, checks the cookie a returning request presents, and
    clears the cookie a logout or a failure must drop. Every method takes the
    request the flow is running, because the cookie is staged on that
    request's own security state — there is no request stack to read the
    current one from, so the caller that holds the request hands it in.

    The cookie each method sets or clears is not returned: it is staged on
    the request, and the response pass moves it onto the response.
    """

    async def create_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        user: UserInterface,
    ) -> None:
        """Stage the remember-me cookie that remembers ``user``.

        Raises:
            AuthenticationError: When the user cannot be remembered — a
                handler that signs its values may refuse one it cannot sign.
        """
        ...

    async def consume_remember_me_cookie(
        self,
        request: ServerRequestInterface,
        remember_me_details: RememberMeDetails,
    ) -> UserInterface:
        """Check the cookie ``remember_me_details`` was read into, and load its user.

        Every cookie is spent by being used: a handler that stores its tokens
        rotates the stored value, and every handler stages a fresh cookie for
        the response to carry back.

        Raises:
            AuthenticationError: When the cookie does not check out — an
                unknown user, a value that no longer counts, a theft.
        """
        ...

    async def clear_remember_me_cookie(self, request: ServerRequestInterface) -> None:
        """Stage the clearing of the remember-me cookie."""
        ...
