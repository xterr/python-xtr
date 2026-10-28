"""Logging a user in by hand, outside the request-driven flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface

__all__ = ["UserAuthenticatorInterface"]


@runtime_checkable
class UserAuthenticatorInterface(Protocol):
    """Authenticates a known user outside the request-driven flow.

    Where the manager's request-driven pass reads a credential off a request,
    this starts from the user itself — a login form that already loaded the
    user, a command that switches to one — and lets one authenticator finish
    the login: create the token, store it, run the success handler and
    announce the login. The passport check, badge validation and the
    post-authentication account check are skipped: the caller vouches for the
    user, so there is nothing to verify.
    """

    async def authenticate_user(
        self,
        user: UserInterface,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        badges: Sequence[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> ResponseInterface | None:
        """Log ``user`` in through ``authenticator`` over ``request``.

        Args:
            user: The user to authenticate, already loaded and vouched for.
            authenticator: The one authenticator to finish the login with.
            request: The request the login answers, as a message.
            badges: Extra badges the passport carries, beyond the user's.
            attributes: Extra attributes the passport carries, handed to the
                token and its listeners.

        Returns:
            The response the success handler or a login-success listener
            produced, or ``None`` when the request goes on.
        """
        ...
