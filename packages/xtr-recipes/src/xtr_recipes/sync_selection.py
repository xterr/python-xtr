"""SyncSelection: which packages a sync configures, updates, undoes or leaves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from .recipe_loader import Recipe
    from .recipe_lock import RecipeLock

__all__ = ["SyncSelection"]


@final
@dataclass(frozen=True, slots=True)
class SyncSelection:
    """The four groups a sync sorts packages into, as names.

    Built by diffing what is installed against what the lock records, which is
    why a sync does not care how a package arrived or left: the difference is
    the work, and running it twice finds none.

    Attributes:
        unconfigure: Locked packages no longer installed, in lock order. Each
            is undone from the lock alone and touches only what it recorded, so
            the order they are undone in does not matter.
        configure: Installed packages the lock has never recorded.
        update: Locked packages whose recipe content has moved on.
        unchanged: Locked packages with nothing to re-apply; their bundle
            standings are still recomputed, because another package arriving
            or leaving changes what requires what.
    """

    unconfigure: tuple[str, ...] = ()
    configure: tuple[str, ...] = ()
    update: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()

    @classmethod
    def diff(
        cls,
        installed: Mapping[str, Recipe],
        lock: RecipeLock,
        held: Collection[str] = (),
    ) -> SyncSelection:
        """Sort every installed and locked package into its group.

        Args:
            installed: Each installed recipe, keyed by distribution.
            lock: What the last sync recorded.
            held: Packages still depended on whose bundle class does not load.
                A locked one is left exactly as the lock has it: a broken or
                partial installation is no reason to delete what was applied.

        Returns:
            The selection a full sync works from.
        """
        return cls(
            unconfigure=tuple(
                name for name in lock.entries if name not in installed and name not in held
            ),
            configure=tuple(sorted(name for name in installed if name not in lock.entries)),
            update=cls._changed(installed, lock, changed=True),
            unchanged=cls._changed(installed, lock, changed=False),
        )

    @classmethod
    def only(cls, package: str, lock: RecipeLock) -> SyncSelection:
        """Select one package, re-applied whether or not its recipe has changed."""
        if package in lock.entries:
            return cls(update=(package,))
        return cls(configure=(package,))

    @classmethod
    def _changed(
        cls,
        installed: Mapping[str, Recipe],
        lock: RecipeLock,
        changed: bool,
    ) -> tuple[str, ...]:
        """Return the locked, installed packages whose recipe hash moved, or did not."""
        return tuple(
            sorted(
                name
                for name, recipe in installed.items()
                if name in lock.entries
                and (lock.entries[name].recipe != recipe.recipe_hash) is changed
            )
        )
