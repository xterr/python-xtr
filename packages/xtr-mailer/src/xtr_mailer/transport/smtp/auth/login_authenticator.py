"""The ``LOGIN`` mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._credentials import base64_line
from .authenticator_interface import AuthenticatorInterface

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.esmtp_transport import EsmtpTransport

__all__ = ["LoginAuthenticator"]


@final
class LoginAuthenticator(AuthenticatorInterface):
    """Answers the server's prompts with the user, then the password, each a line of its own.

    The password crosses the wire merely encoded: use it over TLS.
    """

    @override
    def get_auth_keyword(self) -> str:
        """Return ``LOGIN``."""
        return "LOGIN"

    @override
    async def authenticate(self, client: EsmtpTransport) -> None:
        """Send ``AUTH LOGIN``, then the user and the password as they are asked for."""
        _ = await client.execute_command("AUTH LOGIN", [334])
        _ = await client.execute_command(base64_line(client.get_username()), [334])
        _ = await client.execute_command(base64_line(client.get_password()), [235])
