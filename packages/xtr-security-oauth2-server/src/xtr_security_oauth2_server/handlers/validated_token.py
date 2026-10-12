"""What a handler worked out about the token a client handed it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ValidatedToken"]


@final
@dataclass(frozen=True, repr=False, slots=True)
class ValidatedToken:
    """A token a handler accepted: which kind it turned out to be, and what it says.

    The two kinds this server issues are read in completely different ways —
    an access token is a signed document, a refresh token a payload this
    server sealed — and what comes out of each is a different set of names.
    Carrying the kind beside what was read is what lets everything after the
    reading stay one code path: a handler decides what to withdraw, and a
    document about the token names its fields, by asking which kind it was.

    Attributes:
        token_type: ``access_token`` or ``refresh_token``, as the reading that
            accepted it names its kind.
        token_data: What the token carries — the claims of a signed access
            token, or the payload a refresh token was sealed from.
    """

    token_type: str
    token_data: Mapping[str, object]

    @override
    def __repr__(self) -> str:
        """Name the kind of token, never a word of what it says.

        What the token carries names the resource owner, the client and the
        token itself; none of that belongs in a log line or a traceback.
        """
        return f"<{type(self).__name__} {self.token_type}>"
