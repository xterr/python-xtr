"""Merging the options given to a dump into a dumper's defaults."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

__all__ = ["mapping_at", "replace_recursive"]


def replace_recursive(
    defaults: Mapping[str, object], replacements: Mapping[str, object]
) -> dict[str, object]:
    """Return ``defaults`` with ``replacements`` laid over them, however deep.

    Where both hold a mapping under a key, the two are merged the same way;
    anything else given replaces the default whole. A replaced key keeps the
    place of its default, so a diagram lists its style in a stable order. Every
    mapping returned is a fresh dictionary, so styling one dump never changes
    the defaults of the next.
    """
    merged = {key: _copied(value) for key, value in defaults.items()}
    for key, value in replacements.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = replace_recursive(
                cast("Mapping[str, object]", current), cast("Mapping[str, object]", value)
            )
        else:
            merged[key] = _copied(value)
    return merged


def mapping_at(options: Mapping[str, object], key: str) -> Mapping[str, object]:
    """Return the mapping ``options`` hold under ``key``, empty when they hold none there."""
    value = options.get(key)
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else {}


def _copied(value: object) -> object:
    """Return ``value``, a mapping in it copied to a dictionary, however deep."""
    if isinstance(value, Mapping):
        return {key: _copied(item) for key, item in cast("Mapping[str, object]", value).items()}
    return value
