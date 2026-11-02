"""The ``XOAUTH2`` mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._credentials import base64_line
from .authenticator_interface import AuthenticatorInterface

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.esmtp_transport import EsmtpTransport

__all__ = ["XOAuth2Authenticator"]


@final
class XOAuth2Authenticator(AuthenticatorInterface):
    """Logs in with an OAuth 2.0 access token, which the transport holds as its password.

    The token is the application's to obtain and refresh; this only presents it, as the
    bearer token of the user.
    """

    @override
    def get_auth_keyword(self) -> str:
        """Return ``XOAUTH2``."""
        return "XOAUTH2"

    @override
    async def authenticate(self, client: EsmtpTransport) -> None:
        """Send ``AUTH XOAUTH2`` with the user and the token."""
        credentials = base64_line(
            f"user={client.get_username()}\x01auth=Bearer {client.get_password()}\x01\x01"
        )
        _ = await client.execute_command(f"AUTH XOAUTH2 {credentials}", [235])
