"""TemplateCatalog: the templates shipped with this tool, and any directory holding one."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, final

from .exception import UnknownTemplateError
from .template import MANIFEST, Template

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

__all__ = ["TemplateCatalog"]

_SHIPPED = "xtr_cli.templates"


@final
class TemplateCatalog:
    """Finds a template by the name it ships under, or by a directory on disk.

    The shipped templates live inside this package, so they are the ones
    written for the packages of the same release.
    """

    __slots__ = ("_root",)

    def __init__(self, root: Traversable) -> None:
        """Offer the templates in the subdirectories of ``root``."""
        self._root = root

    @classmethod
    def default(cls) -> TemplateCatalog:
        """Return the catalog of the templates this tool ships."""
        return cls(files(_SHIPPED))

    def names(self) -> tuple[str, ...]:
        """Return the names of the shipped templates, sorted."""
        return tuple(
            sorted(
                entry.name
                for entry in self._root.iterdir()
                if entry.is_dir() and entry.joinpath(MANIFEST).is_file()
            )
        )

    def load(self, template: str) -> Template:
        """Return the shipped template called ``template``, or the one in that directory.

        Raises:
            UnknownTemplateError: When ``template`` is neither a shipped name
                nor a directory holding a ``template.toml``.
            InvalidTemplateError: When the template found cannot be read.
        """
        if template in self.names():
            return Template.load(self._root / template, template)
        directory = Path(template).expanduser()
        if directory.joinpath(MANIFEST).is_file():
            return Template.load(directory, directory.resolve().name)
        raise UnknownTemplateError(template, self.names())
