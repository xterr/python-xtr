"""What every object-store adapter needs that a real filesystem gives for free.

An object store has no directories: there are only keys, and a slash in a key
is a convention the store does not act on. This module holds the handful of
helpers that make one behave like a filesystem to the rest of the package — a
zero-byte object standing in for an empty directory, the rule that tells that
marker apart from a file when a listing hands it back, and an existence check
that answers for a directory the store never recorded. The S3 and object-store
adapters share these so the two answer directory questions the same way.

Private to the adapter package: the helpers take a
:class:`~xtr_storage.adapter._fsspec_bridge.FsspecBridge` and already-prefixed
locations, and know nothing of the caller-facing path or the backend's own API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_storage.adapter._fsspec_bridge import FsspecBridge

__all__ = [
    "directory_exists",
    "directory_marker",
    "is_directory_marker",
    "select_allowed",
]


def directory_marker(location: str) -> str:
    """Return the zero-byte object that stands in for the directory at ``location``.

    A store keeps no empty directory, so one is written as a key ending in a
    slash. The root — an empty location — has no marker to write, and answers
    with an empty string.

    Args:
        location: The directory's already-prefixed location.

    Returns:
        The marker key, ending in a slash, or ``""`` for the root.
    """
    trimmed = location.rstrip("/")
    return f"{trimmed}/" if trimmed else ""


def is_directory_marker(relative_name: str) -> bool:
    """Return whether a listing entry is a directory marker rather than a file.

    A store lists the marker object beside real files when a tree is walked; a
    subdirectory it folds into a name without a trailing slash. The trailing
    slash is therefore what tells a marker apart, and an adapter hides the ones
    that match so a caller never sees the object standing in for a directory.

    Args:
        relative_name: The entry's name with the adapter's root stripped off.

    Returns:
        ``True`` when the name is a marker to hide.
    """
    return relative_name.endswith("/")


def select_allowed(options: Mapping[str, object], allowed: frozenset[str]) -> dict[str, object]:
    """Return the entries of ``options`` a backend understands, dropping the rest.

    A write forwards only the settings its store has a name for; an unknown key
    is dropped here rather than sent on to be refused. The result is a fresh
    dictionary, so a caller may add to it without touching what was configured.

    Args:
        options: The settings a write was configured with.
        allowed: The keys this backend accepts.

    Returns:
        The allowed subset, copied.
    """
    return {key: value for key, value in options.items() if key in allowed}


async def directory_exists(bridge: FsspecBridge, location: str) -> bool:
    """Return whether a directory lives at the already-prefixed ``location``.

    A store keeps no directory to ask after, so it is inferred: the store reports
    a path as a directory precisely when a marker or any key lives under it, and
    as a file when a key sits exactly there. The trailing slash a directory
    location carries is dropped first, because the store resolves ``"a/b/"`` and
    ``"a/b"`` to the same key and would otherwise call a plain file a directory.
    The bare root is a directory by definition, with nothing to look up.

    Args:
        bridge: The filesystem seam to ask.
        location: The directory's already-prefixed location.

    Returns:
        ``True`` when the store reports a directory at ``location``.
    """
    trimmed = location.rstrip("/")
    if not trimmed:
        return True
    try:
        info = await bridge.info(trimmed)
    except FileNotFoundError:
        return False
    return info.get("type") == "directory"
