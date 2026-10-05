"""A manifest table, key or value a recipe cannot be read from."""

from __future__ import annotations

from typing import final

from .recipes_error import RecipesError

__all__ = ["InvalidManifestError"]


@final
class InvalidManifestError(RecipesError, ValueError):
    """A recipe manifest holds something its reader cannot make sense of.

    Raised where the manifest is parsed rather than letting an unknown table,
    an unknown key or a mistyped value through: a recipe that would configure
    an application wrongly should fail at load time, not halfway through a
    sync. The same error reports a template that names a placeholder the
    renderer was never given.

    Also a :class:`ValueError`, so code that already guards parsing with
    ``except ValueError`` keeps working without learning a new exception.

    Attributes:
        package: The distribution whose recipe could not be read.
        key: The table, key, value or template path at fault.
        reason: What about it could not be read.
    """

    package: str
    key: str
    reason: str

    def __init__(self, package: str, key: str, reason: str) -> None:
        """Record which recipe, which key, and why it could not be read."""
        self.package = package
        self.key = key
        self.reason = reason
        super().__init__(f"recipe {package!r}: {key!r} cannot be read: {reason}")
