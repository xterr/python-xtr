"""What the recipe loader reads recipes from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .recipe_content import RecipeContent

__all__ = ["RecipeSourceInterface"]


@runtime_checkable
class RecipeSourceInterface(Protocol):
    """A place recipes come from, keyed by the distribution that ships each.

    Structural on purpose: the default source reads the installed
    distributions' ``xtr_recipes`` entry points, while a test supplies its own
    built from bytes in memory, so the loader is exercised without installing
    anything — a fake, not a mock.
    """

    def load(self) -> Mapping[str, RecipeContent]:
        """Return every available recipe, keyed by normalised distribution name."""
        ...
