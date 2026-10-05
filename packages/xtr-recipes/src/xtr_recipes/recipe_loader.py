"""RecipeLoader: turns a source's raw recipes into parsed, hashed recipes."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from string import Template
from typing import TYPE_CHECKING, final

from .entry_point_recipe_source import EntryPointRecipeSource
from .exception import InvalidManifestError
from .recipe_config import RecipeConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .recipe_content import RecipeContent
    from .recipe_source_interface import RecipeSourceInterface

__all__ = ["Recipe", "RecipeLoader"]


@final
@dataclass(frozen=True, slots=True)
class Recipe:
    """One parsed recipe, ready to apply.

    Attributes:
        distribution: The PEP 503-normalised name of the distribution that
            ships the recipe.
        config: The declarative content, parsed and validated.
        templates: Each template path mapped to its raw bytes.
        recipe_hash: A sha256 over the manifest and every template, so a sync
            re-applies a recipe when its content changes rather than when the
            shared package version is bumped.
    """

    distribution: str
    config: RecipeConfig
    templates: Mapping[str, bytes]
    recipe_hash: str

    def render(self, template: str, *, app: str) -> str:
        """Render a template, substituting ``${app}`` with the application name.

        Args:
            template: The template path, as it appears under ``[files]`` in the
                manifest.
            app: The application import name put in for ``${app}``.

        Returns:
            The rendered text.

        Raises:
            InvalidManifestError: When no such template exists, or the template
                names a placeholder the renderer was not given.
        """
        try:
            raw = self.templates[template]
        except KeyError:
            raise InvalidManifestError(self.distribution, template, "no such template") from None
        body = Template(raw.decode("utf-8"))
        try:
            return body.substitute(app=app)
        except KeyError as missing:
            placeholder = missing.args[0]
            raise InvalidManifestError(
                self.distribution, template, f"unknown placeholder ${{{placeholder}}}"
            ) from missing
        except ValueError as invalid:
            raise InvalidManifestError(self.distribution, template, str(invalid)) from invalid


@final
class RecipeLoader:
    """Loads recipes from a source, parsing and hashing each.

    The default source reads the installed distributions' ``xtr_recipes``
    entry points; a test passes its own so no installation is needed.
    """

    __slots__ = ("_source",)

    def __init__(self, source: RecipeSourceInterface | None = None) -> None:
        """Use ``source`` for discovery, or the entry-point source by default."""
        self._source: RecipeSourceInterface = (
            source if source is not None else EntryPointRecipeSource()
        )

    def load(self) -> tuple[Recipe, ...]:
        """Return every recipe the source offers, parsed, sorted by distribution.

        Raises:
            InvalidManifestError: When a manifest cannot be parsed.
        """
        return tuple(
            _build(distribution, content)
            for distribution, content in sorted(self._source.load().items())
        )


def _build(distribution: str, content: RecipeContent) -> Recipe:
    """Parse one recipe's manifest and compute its hash."""
    try:
        data: dict[str, object] = tomllib.loads(content.manifest.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise InvalidManifestError(distribution, "manifest.toml", str(error)) from error
    return Recipe(
        distribution=distribution,
        config=RecipeConfig.from_toml(distribution, data),
        templates=content.templates,
        recipe_hash=_recipe_hash(content.manifest, content.templates),
    )


def _recipe_hash(manifest: bytes, templates: Mapping[str, bytes]) -> str:
    """Hash the manifest and every template, in sorted path order."""
    digest = hashlib.sha256()
    digest.update(manifest)
    for path in sorted(templates):
        digest.update(path.encode("utf-8"))
        digest.update(templates[path])
    return digest.hexdigest()
