"""RecipeConfig: the declarative content a recipe applies to an application."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from .exception import InvalidManifestError
from .notes_config import NotesConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["RecipeConfig"]

_TABLES = frozenset({"bundles", "files", "env", "gitignore", "notes"})
_NOTES_KEYS = ("steps", "check", "run")
_GITIGNORE_KEYS = frozenset({"lines"})
# A bundle target is "<dotted module>:<ClassName>", exactly as it reads in BUNDLES.
_BUNDLE_TARGET = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*")


@final
@dataclass(frozen=True, slots=True)
class RecipeConfig:
    """Everything a recipe declares, parsed from its ``manifest.toml``.

    Built by :meth:`from_toml`, which is the trust boundary: it is the only
    place untrusted manifest data is turned into these typed fields, so the
    rest of the library receives a value it never has to re-check. A hand-built
    instance is trusted as given.

    Attributes:
        bundles: Each bundle target (``"module:Class"``) mapped to the
            environment flags it is listed with, as they appear in ``BUNDLES``.
        files: Each destination, relative to the application package, mapped to
            its template path relative to the recipe.
        env: Each environment variable mapped to its default, ``""`` meaning no
            default (written commented out so the variable stays unset).
        gitignore: The ``.gitignore`` lines the recipe contributes.
        notes: What the recipe prints rather than does.
    """

    bundles: Mapping[str, Mapping[str, bool]] = field(default_factory=dict)
    files: Mapping[str, str] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)
    gitignore: tuple[str, ...] = ()
    notes: NotesConfig = field(default_factory=NotesConfig)

    @classmethod
    def from_toml(cls, package: str, data: Mapping[str, object]) -> RecipeConfig:
        """Parse one recipe's manifest, validating every table, key and value.

        Args:
            package: The distribution whose manifest this is, named in errors.
            data: The manifest, already read from TOML into a mapping.

        Returns:
            The parsed, validated recipe content.

        Raises:
            InvalidManifestError: On an unknown table, an unknown key, a
                malformed ``"module:Class"`` bundle target, or a value of the
                wrong type — each naming the package and the key at fault.
        """
        unknown = sorted(set(data) - _TABLES)
        if unknown:
            raise InvalidManifestError(package, unknown[0], "unknown table")
        return cls(
            bundles=_read_bundles(package, data.get("bundles")),
            files=_read_strings(package, "files", data.get("files")),
            env=_read_strings(package, "env", data.get("env")),
            gitignore=_read_gitignore(package, data.get("gitignore")),
            notes=_read_notes(package, data.get("notes")),
        )


def _as_table(package: str, key: str, value: object) -> dict[str, object]:
    """Return ``value`` as a table of string keys, or ``{}`` when absent."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise InvalidManifestError(package, key, "must be a table")
    table: dict[str, object] = {}
    for name, item in value.items():
        if not isinstance(name, str):
            raise InvalidManifestError(package, key, "every key must be a string")
        table[name] = item
    return table


def _read_bundles(package: str, value: object) -> dict[str, dict[str, bool]]:
    """Parse the ``[bundles]`` table: each target mapped to its flags."""
    result: dict[str, dict[str, bool]] = {}
    for target, flags in _as_table(package, "bundles", value).items():
        if _BUNDLE_TARGET.fullmatch(target) is None:
            raise InvalidManifestError(package, target, "expected '<module>:<Class>'")
        result[target] = _read_flags(package, target, flags)
    return result


def _read_flags(package: str, target: str, value: object) -> dict[str, bool]:
    """Parse one bundle's environment flags: a table of booleans."""
    result: dict[str, bool] = {}
    for name, flag in _as_table(package, target, value).items():
        if not isinstance(flag, bool):
            raise InvalidManifestError(package, f"{target}.{name}", "flag must be true or false")
        result[name] = flag
    return result


def _read_strings(package: str, key: str, value: object) -> dict[str, str]:
    """Parse a table whose every value must be a string."""
    result: dict[str, str] = {}
    for name, item in _as_table(package, key, value).items():
        if not isinstance(item, str):
            raise InvalidManifestError(package, f"{key}.{name}", "must be a string")
        result[name] = item
    return result


def _read_gitignore(package: str, value: object) -> tuple[str, ...]:
    """Parse the ``[gitignore]`` table: only a ``lines`` list of strings."""
    table = _as_table(package, "gitignore", value)
    unknown = sorted(set(table) - _GITIGNORE_KEYS)
    if unknown:
        raise InvalidManifestError(package, f"gitignore.{unknown[0]}", "unknown key")
    return _read_str_list(package, "gitignore.lines", table.get("lines"))


def _read_notes(package: str, value: object) -> NotesConfig:
    """Parse the ``[notes]`` table: only ``steps``, ``check`` and ``run`` lists."""
    table = _as_table(package, "notes", value)
    unknown = sorted(set(table) - set(_NOTES_KEYS))
    if unknown:
        raise InvalidManifestError(package, f"notes.{unknown[0]}", "unknown key")
    return NotesConfig(
        steps=_read_str_list(package, "notes.steps", table.get("steps")),
        check=_read_str_list(package, "notes.check", table.get("check")),
        run=_read_str_list(package, "notes.run", table.get("run")),
    )


def _read_str_list(package: str, key: str, value: object) -> tuple[str, ...]:
    """Return ``value`` as a tuple of strings, or ``()`` when absent."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise InvalidManifestError(package, key, "must be a list")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise InvalidManifestError(package, key, "every entry must be a string")
        items.append(item)
    return tuple(items)
