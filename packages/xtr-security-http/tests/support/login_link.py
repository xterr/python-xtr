"""Login-link fakes: a handler that records what a test asked of it."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

from xtr_security_http.exception import InvalidLoginLinkError, InvalidLoginLinkErrorInterface
from xtr_security_http.login_link.login_link_details import LoginLinkDetails

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["RecordingLoginLinkHandler"]


@final
class RecordingLoginLinkHandler:
    """Answers the links a test configured, recording every call.

    The fake's consume answers with the user the test registered, or
    refuses the link with the error the test registered — the two
    outcomes a presented link has.
    """

    __slots__ = ("consumed", "created", "error", "user")

    def __init__(
        self,
        user: UserInterface | None = None,
        error: InvalidLoginLinkErrorInterface | None = None,
    ) -> None:
        self.user = user
        self.error = error
        self.created: list[tuple[UserInterface, ServerRequestInterface | None]] = []
        self.consumed: list[ServerRequestInterface] = []

    async def create_login_link(
        self,
        user: UserInterface,
        request: ServerRequestInterface | None = None,
        lifetime: int | None = None,
        parameters: Mapping[str, str | bool | int | float] | None = None,
    ) -> LoginLinkDetails:
        """Record the minting, and answer with a link of the fake's own."""
        del lifetime, parameters
        self.created.append((user, request))
        return LoginLinkDetails("/login-link", datetime(2024, 4, 9, 12, tzinfo=UTC))

    async def consume_login_link(self, request: ServerRequestInterface) -> UserInterface:
        """Record the request, and answer as the test configured.

        Raises:
            InvalidLoginLinkError: When the test configured no user for
                the link to sign in.
        """
        self.consumed.append(request)
        if self.error is not None:
            raise self.error
        if self.user is None:
            raise InvalidLoginLinkError("The fake handler was configured with no user.")
        return self.user
