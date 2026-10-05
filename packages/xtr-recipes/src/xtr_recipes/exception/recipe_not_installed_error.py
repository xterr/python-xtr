"""The package named for a single-recipe run has no recipe to apply."""

from __future__ import annotations

from typing import final

from .recipes_error import RecipesError

__all__ = ["RecipeNotInstalledError"]


@final
class RecipeNotInstalledError(RecipesError):
    """One package was named to configure, and it is not one that can be.

    A full sync works from what is installed, so it has nothing to report
    about a package that is not. Naming one explicitly is different: the
    answer must be an error rather than a silent plan of nothing, because the
    cause is usually a package the application does not depend on, or one
    installed without the recipe that configures it.

    Attributes:
        package: The distribution that was named.
    """

    package: str

    def __init__(self, package: str) -> None:
        """Record the distribution that has no recipe to apply."""
        self.package = package
        reason = "it is not a direct dependency of this application, or it ships no recipe"
        super().__init__(f"{package} has no recipe to apply: {reason}")
