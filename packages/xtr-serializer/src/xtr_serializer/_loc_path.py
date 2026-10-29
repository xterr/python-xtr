"""Where a value sits, written as a reader of the data spells it: ``items[0].price``."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["render_path"]


def render_path(keys: Iterable[str | int]) -> str | None:
    """Join the keys and indexes leading to a value into a path, or ``None`` for the root.

    pydantic locates an error by a tuple of keys and indexes; errors here carry it as one string,
    the way the data would be addressed in code, so every error reads its path the same way.
    """
    path = "".join(f"[{key}]" if isinstance(key, int) else f".{key}" for key in keys)
    return path.removeprefix(".") or None
