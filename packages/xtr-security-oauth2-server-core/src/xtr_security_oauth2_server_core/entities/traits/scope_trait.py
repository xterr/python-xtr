"""A scope reads as the identifier it is named by."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

__all__ = ["ScopeTrait"]


class ScopeTrait:
    """Makes a scope read as its identifier.

    Compose it with the identifier trait and a scope entity is complete. What
    it buys is serialisation: the encrypted code and refresh-token payloads and
    the token responses write a set of scopes out with
    ``json.dumps(scopes, default=str)``, and each one lands as its name rather
    than as an object nothing on the other side could read.
    """

    if TYPE_CHECKING:
        # Declared for the type checker, never defined here: whatever composes
        # this trait brings it — the identifier trait does, and a mapped entity
        # may bring its own — and at runtime the name resolves to that.
        def get_identifier(self) -> str:
            """Return the identifier this scope is named by."""
            ...

    @override
    def __str__(self) -> str:
        """Return the identifier, so a scope reads and serialises as its name."""
        return self.get_identifier()
