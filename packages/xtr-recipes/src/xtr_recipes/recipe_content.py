"""RecipeContent: the raw bytes of one recipe, before it is parsed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RecipeContent"]


@final
@dataclass(frozen=True, slots=True)
class RecipeContent:
    """One recipe as a source hands it over: unparsed manifest and templates.

    This is the boundary between discovering recipes and interpreting them. A
    source — the installed entry points, or a fake in a test — produces these,
    and the loader turns each into a :class:`~xtr_recipes.recipe_loader.Recipe`.
    Keeping the raw bytes lets the loader hash exactly what shipped.

    Attributes:
        manifest: The raw ``manifest.toml`` bytes.
        templates: Each template path, relative to the recipe, mapped to its
            raw bytes.
    """

    manifest: bytes
    templates: Mapping[str, bytes]
