"""One scope a client is registered for, or a token was granted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from typing_extensions import override

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError

__all__ = ["Scope"]


@final
@dataclass(frozen=True, slots=True)
class Scope:
    """A scope, named by its identifier.

    This is the stored side of a scope: what a client's registration lists,
    what a deployment makes available, and what a token was granted once it
    was written down. The library's own scope entity is the other side, and
    the scope converter turns one into the other.

    Two scopes of one name are the same scope, which is what lets a requested
    set be checked against a client's set by containment, and lets a set of
    them be deduplicated.
    """

    scope: str

    def __post_init__(self) -> None:
        """Refuse a scope with no name.

        Raises:
            InvalidArgumentError: When ``scope`` is empty.
        """
        if self.scope == "":
            raise InvalidArgumentError(
                "A scope has to be named; an empty scope would be written into a token "
                "as a permission nothing can grant or check.",
            )

    @override
    def __str__(self) -> str:
        """Return the identifier, so a scope reads and serialises as its name."""
        return self.scope
