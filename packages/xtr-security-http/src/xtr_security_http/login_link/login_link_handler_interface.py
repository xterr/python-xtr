"""What mints a login link, and what a followed one answers with."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

    from .login_link_details import LoginLinkDetails

__all__ = ["LoginLinkHandlerInterface"]


@runtime_checkable
class LoginLinkHandlerInterface(Protocol):
    """Creates the links a login is asked to arrive by, and consumes them.

    A login link is a URL the handler signs for one user until one
    moment; presenting it back is the login. The handler is the one voice
    on what a link carries: it mints one for a user, and checks the one a
    request presents, loading the user the link was signed for.
    """

    async def create_login_link(
        self,
        user: UserInterface,
        request: ServerRequestInterface | None = None,
        lifetime: int | None = None,
        parameters: Mapping[str, str | bool | int | float] | None = None,
    ) -> LoginLinkDetails:
        """Mint a link that authenticates as ``user``, until it expires.

        Args:
            user: The user the link signs in.
            request: The request the link is generated against, when there
                is one — the link's URI is built for that request's own
                address.
            lifetime: How long the link counts, in seconds; the handler's
                configured lifetime when ``None``.
            parameters: Extra query parameters the link carries, covered
                by its hash.

        Raises:
            InvalidArgumentError: When a parameter's name is malformed or
                reserved, or the handler's configured path is a route
                name.
        """
        ...

    async def consume_login_link(self, request: ServerRequestInterface) -> UserInterface:
        """Check the link ``request`` presents, and load the user it signs in.

        The extra parameters the link carried are exposed on the
        request's security state under the login-link parameters key,
        for the handlers that answer the login.

        Raises:
            InvalidLoginLinkError: When the link does not check out — a
                parameter missing or malformed, a hash that verifies
                under no secret, a user the provider does not know.
            ExpiredLoginLinkError: When the link's moment has passed.
        """
        ...
