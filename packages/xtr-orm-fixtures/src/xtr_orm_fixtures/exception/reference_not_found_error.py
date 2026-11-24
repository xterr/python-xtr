"""A reference was asked for by a name nothing was stored under."""

from __future__ import annotations

from .orm_fixtures_error import OrmFixturesError

__all__ = ["ReferenceNotFoundError"]


class ReferenceNotFoundError(OrmFixturesError, LookupError):
    """A reference was asked for by a name nothing was stored under.

    Also a :class:`LookupError`, as a missing key in any other mapping is.

    Attributes:
        name: The name asked for.
        kind: The class the reference was asked for as, by name.
    """

    name: str
    kind: str

    def __init__(self, name: str, kind: str) -> None:
        """Record the name and the class asked for."""
        self.name = name
        self.kind = kind
        super().__init__(f'No reference named "{name}" was stored for "{kind}".')
