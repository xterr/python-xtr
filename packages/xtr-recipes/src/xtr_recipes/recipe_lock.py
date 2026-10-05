"""Reading and writing ``xtr.lock``, the record of what each recipe applied."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypeAlias, final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

__all__ = ["BundleState", "LockEntry", "LockedFile", "RecipeLock"]

BundleState: TypeAlias = Literal["listed", "adopted", "required"]
"""How a recipe's bundle came to be in ``BUNDLES``.

``listed`` when the sync added it, ``adopted`` when it was already there, and
``required`` when another listed bundle requires it, so the sync leaves it out.
"""

_LOCK_NAME = "xtr.lock"


@final
@dataclass(frozen=True, slots=True)
class LockedFile:
    """A file a recipe wrote, as the lock remembers it.

    Attributes:
        sha256: The hash of the content the recipe wrote, telling an untouched
            file from one the application owner has since edited.
        adopted: Whether the file was already present when the recipe first
            ran, and so must never be deleted on removal.
    """

    sha256: str
    adopted: bool


@final
@dataclass(frozen=True, slots=True)
class LockEntry:
    """What one recipe applied to the project.

    Attributes:
        recipe: The recipe hash in force when it was applied.
        bundles: Each bundle target mapped to how it entered ``BUNDLES``.
        files: Each written file path mapped to what was written.
        env: The environment keys the sync wrote inside its own block; adopted
            keys are not recorded, so they are never removed.
        gitignore: The ignore lines the sync wrote inside its own block.
    """

    recipe: str = ""
    bundles: Mapping[str, BundleState] = field(default_factory=dict)
    files: Mapping[str, LockedFile] = field(default_factory=dict)
    env: tuple[str, ...] = ()
    gitignore: tuple[str, ...] = ()


@final
@dataclass(frozen=True, slots=True)
class RecipeLock:
    """The whole ``xtr.lock``: every applied recipe, keyed by distribution.

    The lock alone is enough to undo a recipe after its package is removed, so
    it records paths relative to the project directory, ``/``-separated.
    """

    entries: Mapping[str, LockEntry] = field(default_factory=dict)

    @classmethod
    def load(cls, project_dir: Path) -> RecipeLock:
        """Read ``xtr.lock`` from ``project_dir``; a missing file is an empty lock."""
        path = project_dir / _LOCK_NAME
        if not path.is_file():
            return cls({})
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return cls({})
        entries: dict[str, LockEntry] = {}
        for name, value in raw.items():
            entries[str(name)] = _entry(value)
        return cls(entries)

    def write(self, project_dir: Path) -> None:
        """Write ``xtr.lock`` into ``project_dir``: sorted keys, 2-space, newline-ended."""
        _ = (project_dir / _LOCK_NAME).write_text(self.dumps(), encoding="utf-8")

    def dumps(self) -> str:
        """Return the exact text :meth:`write` would write: sorted, 2-space, newline-ended.

        A sync compares this against the file already on disk, so it writes the
        lock only when the lock actually changed — the difference between a
        ``--check`` that passes and one that fails.
        """
        return f"{json.dumps(self._to_json(), sort_keys=True, indent=2)}\n"

    def _to_json(self) -> dict[str, dict[str, object]]:
        """Return the lock as the JSON-ready mapping ``write`` serialises."""
        return {
            name: {
                "recipe": entry.recipe,
                "bundles": dict(entry.bundles),
                "files": {
                    path: {"sha256": locked.sha256, "adopted": locked.adopted}
                    for path, locked in entry.files.items()
                },
                "env": list(entry.env),
                "gitignore": list(entry.gitignore),
            }
            for name, entry in self.entries.items()
        }


def _entry(value: object) -> LockEntry:
    """Build one lock entry from its JSON object, tolerating a foreign shape."""
    table = value if isinstance(value, dict) else {}
    return LockEntry(
        recipe=_as_str(table.get("recipe")),
        bundles=_as_bundles(table.get("bundles")),
        files=_as_files(table.get("files")),
        env=_as_str_tuple(table.get("env")),
        gitignore=_as_str_tuple(table.get("gitignore")),
    )


def _as_bundles(value: object) -> dict[str, BundleState]:
    """Read a bundles table, keeping only recognised states."""
    result: dict[str, BundleState] = {}
    if isinstance(value, dict):
        for key, state in value.items():
            resolved = _as_state(state)
            if resolved is not None:
                result[str(key)] = resolved
    return result


def _as_state(value: object) -> BundleState | None:
    """Return a bundle state, or ``None`` for anything unrecognised."""
    match value:
        case "listed":
            return "listed"
        case "adopted":
            return "adopted"
        case "required":
            return "required"
        case _:
            return None


def _as_files(value: object) -> dict[str, LockedFile]:
    """Read a files table into typed entries, skipping malformed ones."""
    result: dict[str, LockedFile] = {}
    if isinstance(value, dict):
        for path, locked in value.items():
            if isinstance(locked, dict):
                result[str(path)] = LockedFile(
                    sha256=_as_str(locked.get("sha256")),
                    adopted=locked.get("adopted") is True,
                )
    return result


def _as_str(value: object) -> str:
    """Return ``value`` when it is a string, otherwise the empty string."""
    return value if isinstance(value, str) else ""


def _as_str_tuple(value: object) -> tuple[str, ...]:
    """Return ``value`` as a tuple of its string entries."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
