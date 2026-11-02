"""The ``CRAM-MD5`` mechanism."""

from __future__ import annotations

import base64
import hmac
import re
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_mailer.exception import InvalidArgumentError

from ._credentials import base64_line, utf8
from .authenticator_interface import AuthenticatorInterface

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.esmtp_transport import EsmtpTransport

__all__ = ["CramMd5Authenticator"]

_NOT_BASE64: Final = re.compile(r"[^A-Za-z0-9+/]")
_CODE_LENGTH: Final = 4  # "334 " before the challenge


@final
class CramMd5Authenticator(AuthenticatorInterface):
    """Answers the server's challenge with a digest keyed by the password, never the password.

    RFC 2195: the reply is the user and the HMAC-MD5 of the challenge, in hex.
    """

    @override
    def get_auth_keyword(self) -> str:
        """Return ``CRAM-MD5``."""
        return "CRAM-MD5"

    @override
    async def authenticate(self, client: EsmtpTransport) -> None:
        """Send ``AUTH CRAM-MD5`` and answer the challenge.

        Raises:
            InvalidArgumentError: The password is empty; nothing is sent.
        """
        secret = client.get_password()
        if not secret:
            raise InvalidArgumentError("A non-empty secret is required.")
        key = utf8(secret)
        reply = await client.execute_command("AUTH CRAM-MD5", [334])
        digest = hmac.new(key, _challenge(reply[_CODE_LENGTH:]), "md5").hexdigest()
        _ = await client.execute_command(base64_line(f"{client.get_username()} {digest}"), [235])


def _challenge(text: str) -> bytes:
    """Decode the challenge leniently: a server's stray characters or padding never raise.

    Whatever is not a base64 digit is dropped, a lone digit left over (it encodes no whole
    byte) too, and the rest is padded to whole groups; a server sending nonsense gets a
    digest of it, which it then refuses.
    """
    digits = _NOT_BASE64.sub("", text)
    if len(digits) % 4 == 1:
        digits = digits[:-1]
    return base64.b64decode(digits + "=" * (-len(digits) % 4))
