"""The one call a login makes to the session it reattached."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["SessionAuthenticationStrategyInterface"]


@runtime_checkable
class SessionAuthenticationStrategyInterface(Protocol):
    """Updates the session after a successful authentication.

    A login is the moment a session's ID is most worth stealing: the
    account it now carries is the prize. What the session itself must do
    about that — carry its attributes to a fresh ID, or empty out
    entirely — is this interface's one call, made while the request that
    authenticated is still the one being answered, so the ID the
    response re-issues is the rotated one.
    """

    async def on_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> None:
        """Perform whatever changes the login asks of the session.

        Args:
            request: The request that authenticated, carrying the session
                on its security state.
            token: The token the authentication settled on.
        """
        ...
