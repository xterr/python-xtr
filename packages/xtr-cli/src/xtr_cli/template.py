"""Template: the files a project starts with, and the packages it is made of."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import PurePosixPath
from string import Template as Placeholders
from typing import TYPE_CHECKING, final

from .exception import InvalidTemplateError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from importlib.resources.abc import Traversable

__all__ = ["MANIFEST", "Template"]

MANIFEST = "template.toml"
"""The file that makes a directory a template."""

_TABLES = frozenset({"summary", "dependencies", "files", "notes"})
_DEPENDENCY_KEYS = frozenset({"packages", "dev"})
_NOTE_KEYS = frozenset({"next"})


@final
@dataclass(frozen=True, slots=True)
class Template:
    """A project template, read from a directory holding a ``template.toml``.

    A template writes only what no package's recipe can write: the project's
    manifest, its kernel and its entry points. The bundle list, the ``.env``
    file and the ignore lines are left to the recipes of the packages it names,
    applied once they are installed — so a new project is already in the state
    ``recipes:sync --check`` expects.

    The manifest::

        summary = "A console application."

        [dependencies]
        packages = ["xtr-console[di]"]   # installed with `uv add`
        dev = ["xtr-recipes"]            # installed with `uv add --dev`

        [files]
        # destination in the project = template under this directory
        "src/${app}/kernel.py" = "files/kernel.py.tmpl"

        [notes]
        next = ["uv run ${name} list"]   # printed once the project is made

    Destinations, file contents and notes substitute ``${name}`` (the
    distribution), ``${app}`` (the import name), ``${python}`` (``3.13``) and
    ``${minor}`` (``13``) with :meth:`string.Template.substitute`; a literal
    ``$`` is written ``$$``.

    Attributes:
        name: The template's name — the name of its directory.
        summary: One line on what it makes.
        dependencies: The requirements every project made from it starts with.
        dev_dependencies: The development requirements it starts with.
        files: Each destination pattern mapped to the template text written there.
        next_steps: Commands to try once the project is made.
    """

    name: str
    summary: str
    dependencies: tuple[str, ...]
    dev_dependencies: tuple[str, ...]
    files: tuple[tuple[str, str], ...]
    next_steps: tuple[str, ...]

    @classmethod
    def load(cls, root: Traversable, name: str) -> Template:
        """Read the template in ``root``, called ``name``.

        Raises:
            InvalidTemplateError: When the manifest does not parse, holds an
                unknown table or key or a value of the wrong type, or names a
                template file that is not there.
        """
        try:
            data = tomllib.loads((root / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            raise InvalidTemplateError(name, f"{MANIFEST} cannot be read: {error}") from error
        _only(name, "the manifest", data, _TABLES)
        summary = data.get("summary", "")
        if not isinstance(summary, str):
            raise InvalidTemplateError(name, "summary must be a string")
        dependencies = _table(name, data, "dependencies", _DEPENDENCY_KEYS)
        notes = _table(name, data, "notes", _NOTE_KEYS)
        return cls(
            name=name,
            summary=summary,
            dependencies=_strings(name, dependencies, "dependencies.packages"),
            dev_dependencies=_strings(name, dependencies, "dependencies.dev"),
            files=_files(name, root, data),
            next_steps=_strings(name, notes, "notes.next"),
        )

    def render(self, values: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
        """Return every file this template writes, as ``(path, text)``, with ``values`` in.

        Raises:
            InvalidTemplateError: When a destination or a file holds a
                placeholder ``values`` does not have, or a destination leaves
                the project directory.
        """
        rendered: list[tuple[str, str]] = []
        for pattern, text in self.files:
            destination = self._substitute(pattern, values, f"destination {pattern!r}")
            path = PurePosixPath(destination)
            if path.is_absolute() or ".." in path.parts:
                raise InvalidTemplateError(self.name, f"{destination!r} leaves the project")
            rendered.append((str(path), self._substitute(text, values, f"file {pattern!r}")))
        return tuple(rendered)

    def steps(self, values: Mapping[str, str]) -> tuple[str, ...]:
        """Return the next steps with ``values`` in.

        Raises:
            InvalidTemplateError: When a step holds a placeholder ``values``
                does not have.
        """
        return tuple(self._substitute(step, values, "notes.next") for step in self.next_steps)

    def _substitute(self, text: str, values: Mapping[str, str], where: str) -> str:
        try:
            return Placeholders(text).substitute(values)
        except KeyError as error:
            raise InvalidTemplateError(
                self.name, f"{where}: unknown placeholder {error}"
            ) from error
        except ValueError as error:
            raise InvalidTemplateError(self.name, f"{where}: {error}") from error


def _only(name: str, where: str, data: Mapping[str, object], allowed: frozenset[str]) -> None:
    """Refuse a key ``allowed`` does not hold, so a typo is not silently ignored."""
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise InvalidTemplateError(name, f"unknown key {unknown[0]!r} in {where}")


def _table(
    name: str, data: Mapping[str, object], key: str, allowed: frozenset[str]
) -> Mapping[str, object]:
    """Return the table ``key``, empty when absent, holding nothing but ``allowed``."""
    table = data.get(key, {})
    if not isinstance(table, dict):
        raise InvalidTemplateError(name, f"{key} must be a table")
    _only(name, f"[{key}]", table, allowed)
    return table


def _strings(name: str, table: Mapping[str, object], dotted: str) -> tuple[str, ...]:
    """Return the list of strings at ``dotted``'s last part, empty when absent."""
    value = table.get(dotted.rpartition(".")[2], [])
    if not isinstance(value, list) or not all(isinstance(each, str) for each in value):
        raise InvalidTemplateError(name, f"{dotted} must be a list of strings")
    return tuple(value)


def _files(name: str, root: Traversable, data: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Return each destination mapped to the text of the template file it names."""
    table = data.get("files", {})
    if not isinstance(table, dict):
        raise InvalidTemplateError(name, "files must be a table")
    files: list[tuple[str, str]] = []
    for destination, source in table.items():
        if not isinstance(source, str):
            raise InvalidTemplateError(name, f"files.{destination!r} must name a file")
        found = root.joinpath(*PurePosixPath(source).parts)
        if ".." in PurePosixPath(source).parts or not found.is_file():
            raise InvalidTemplateError(name, f"files.{destination!r}: no file {source!r}")
        files.append((destination, found.read_text(encoding="utf-8")))
    return tuple(files)
