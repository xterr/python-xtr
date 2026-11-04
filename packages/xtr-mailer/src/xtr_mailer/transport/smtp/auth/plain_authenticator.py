"""The ``PLAIN`` mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._credentials import base64_line
from .authenticator_interface import AuthenticatorInterface

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.esmtp_transport import EsmtpTransport

__all__ = ["PlainAuthenticator"]


@final
class PlainAuthenticator(AuthenticatorInterface):
    """Sends the user, as itself and as the identity to act for, and the password, in one line.

    The password crosses the wire merely encoded: use it over TLS. RFC 4954.
    """

    @override
    def get_auth_keyword(self) -> str:
        """Return ``PLAIN``."""
        return "PLAIN"

    @override
    async def authenticate(self, client: EsmtpTransport) -> None:
        """Send ``AUTH PLAIN`` with the credentials."""
        username = client.get_username()
        credentials = base64_line(f"{username}\0{username}\0{client.get_password()}")
        _ = await client.execute_command(f"AUTH PLAIN {credentials}", [235])
