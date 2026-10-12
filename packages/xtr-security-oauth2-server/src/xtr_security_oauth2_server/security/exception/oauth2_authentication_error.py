"""A request carrying an access token this server will not accept."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final

from xtr_security_core.exception import AuthenticationError
from xtr_security_oauth2_server_core.bearer_challenge import bearer_challenge
from xtr_security_oauth2_server_core.exception.oauth2_error import OAuth2Error

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["OAuth2AuthenticationError"]

#: What RFC 6750 section 3.1 calls a token that is "expired, revoked,
#: malformed, or invalid for other reasons", and what RFC 9068 section 4
#: requires the answer to a failed check to name.
_INVALID_TOKEN: Final[str] = "invalid_token"  # noqa: S105 -- an error code the standard names, not a secret


class OAuth2AuthenticationError(  # pyright: ignore[reportUnsafeMultipleInheritance]  -- both bases are exceptions, and the family's __init__ walks the chain to this package's base
    AuthenticationError,
    OAuth2Error,
):
    """An access token was presented, and reading it did not establish a caller.

    It is both kinds of error at once, and has to be. The firewall only answers
    the security family's own failures, so this derives from the family's
    ``AuthenticationError`` to be answered at all; and one ``except
    OAuth2Error`` has to keep catching everything this package raises, so it
    derives from that base too.

    Both bases are exceptions, so both end at ``BaseException``; the family's
    own ``__init__`` is the one that runs, and it calls up the chain, so this
    package's base is initialised too.

    It carries the status and the challenge the answer is made of, because the
    caller is owed both: the status says the request was refused, and the
    challenge says what would have worked.

    Attributes:
        status_code: The status the refusal is answered with.
    """

    MESSAGE_KEY: ClassVar[str] = "The access token could not be accepted."

    status_code: int

    def __init__(
        self,
        message: str,
        status_code: int,
        *,
        message_key: str | None = None,
    ) -> None:
        """Refuse with ``status_code``, saying ``message`` internally.

        Args:
            message: What went wrong, for a log and a traceback. It may name
                the token, the client or the reason, so it is never sent.
            status_code: The status the refusal is answered with.
            message_key: The safe, public text a caller may be shown; the
                class's own when left out.
        """
        super().__init__(message, message_key=message_key)
        self.status_code = status_code

    def get_status_code(self) -> int:
        """Return the status this refusal is answered with."""
        return self.status_code

    def get_headers(self) -> Mapping[str, str]:
        """Return the challenge the refusal carries.

        Always a bearer challenge: this server accepts its access tokens in no
        other way, so telling a caller to present one is the whole of what it
        can suggest.

        It names ``invalid_token``, which RFC 9068 section 4 requires of the
        answer to any failed validation check and RFC 6750 section 3 asks for
        whenever a request did present a token and failed authentication. The
        description beside it is the public text, which is the same for every
        unusable token: which check it was stays in the exception, so the
        answer cannot be read as a way of probing what this server holds.
        """
        return {
            "WWW-Authenticate": bearer_challenge(
                "error",
                _INVALID_TOKEN,
                error_description=self.get_message_key(),
            ),
        }
