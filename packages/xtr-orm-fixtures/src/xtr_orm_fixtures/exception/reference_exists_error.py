"""A reference was added under a name already taken."""

from __future__ import annotations

from .orm_fixtures_error import OrmFixturesError

__all__ = ["ReferenceExistsError"]


class ReferenceExistsError(OrmFixturesError):
    """A reference was added under a name already taken.

    Adding refuses to replace; setting replaces on purpose.

    Attributes:
        name: The name already taken.
        kind: The class the reference is stored for, by name.
    """

    name: str
    kind: str

    def __init__(self, name: str, kind: str) -> None:
        """Record the name taken and the class it is stored for."""
        self.name = name
        self.kind = kind
        super().__init__(
            f'A reference named "{name}" is already stored for "{kind}"; '
            "use set_reference to replace it."
        )
