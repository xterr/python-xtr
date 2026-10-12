"""One redirect URI a client is registered with, checked when it is made."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, final

from typing_extensions import override

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["RedirectUri"]

#: What counts as a URI here: a scheme, then either an authority with an
#: optional path, or an absolute path, or nothing — then an optional query and
#: fragment, and no whitespace anywhere. It is deliberately not a full RFC 3986
#: grammar: a native client registers something like ``com.example.app:/cb``,
#: which a parser expecting ``//`` would refuse, while an open redirect comes
#: from a loose *comparison*, not from a loose spelling.
_URI: Final[re.Pattern[str]] = re.compile(
    r"[a-zA-Z][a-zA-Z0-9+.-]*:(?://[^/\s?#]+(?:/[^\s?#]*)?|/[^\s?#]*)?(?:\?[^\s#]*)?(?:#\S*)?",
)


@final
@dataclass(frozen=True, slots=True)
class RedirectUri:
    """A redirect URI a client may be sent back to.

    Checked here rather than where it is used, so everything downstream — the
    stored registration, a listing narrowed by URI, the exact-match comparison
    an authorization request is validated by — works on something that is
    already a URI. A registration that would never match anything is refused
    when it is written instead of failing one request at a time.
    """

    redirect_uri: str

    def __post_init__(self) -> None:
        """Refuse anything that is not a URI.

        Raises:
            InvalidArgumentError: When ``redirect_uri`` is not one.
        """
        if _URI.fullmatch(self.redirect_uri) is None:
            raise InvalidArgumentError(
                f"The string {self.redirect_uri!r} is not a valid URI, so no client could "
                "ever be redirected to it.",
            )

    @override
    def __str__(self) -> str:
        """Return the URI, so a redirect URI reads and serialises as itself."""
        return self.redirect_uri
