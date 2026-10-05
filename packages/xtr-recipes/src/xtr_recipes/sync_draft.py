"""SyncDraft: every decision one sync has made, read as steps or as a lock."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, final

from .operation.bundle_note import BundleNote
from .operation.section import Section
from .recipe_lock import LockEntry, RecipeLock
from .sync_selection import SyncSelection

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .operation.operation_interface import OperationInterface
    from .planned_recipe import PlannedRecipe
    from .recipe_loader import Recipe
    from .recipe_lock import BundleState

__all__ = ["SyncDraft"]

_STATE_NOTES: Mapping[BundleState, str] = {
    "listed": "listed",
    "adopted": "already listed",
    "required": "required by another bundle",
}


def _no_recipes() -> dict[str, Recipe]:
    """No installed recipes."""
    return {}


def _no_planned() -> dict[str, PlannedRecipe]:
    """No package planned."""
    return {}


def _no_steps() -> dict[str, tuple[OperationInterface, ...]]:
    """No package undone."""
    return {}


def _no_targets() -> dict[str, tuple[str, ...]]:
    """No package skipped."""
    return {}


def _no_states() -> dict[str, BundleState]:
    """No bundle put forward."""
    return {}


@final
@dataclass(frozen=True, slots=True)
class SyncDraft:
    """A sync with every package decided, before any of it is put in order.

    Two things are read off it, and they must agree: the steps it reports and
    the lock it would leave behind. Keeping both here is what makes them agree
    — the standing a bundle is reported with is the one recorded, and a file
    reported as kept is the one the lock keeps as it was.

    Attributes:
        selection: Which packages the sync configures, updates, undoes or
            leaves alone.
        installed: Each installed recipe, keyed by distribution.
        planned: What each configured or re-applied recipe would do.
        undone: The steps that undo each package being unconfigured.
        skipped: Each package whose bundle class the installation does not
            carry, mapped to the targets that could not be loaded.
        states: Each candidate bundle's standing in the final list.
        lock: The lock as the last sync left it.
        listed: The bundle targets the application's list held before the run,
            so an unconfigured package's bundles are only reported as removed
            when they were there to remove.
    """

    selection: SyncSelection = field(default_factory=SyncSelection)
    installed: Mapping[str, Recipe] = field(default_factory=_no_recipes)
    planned: Mapping[str, PlannedRecipe] = field(default_factory=_no_planned)
    undone: Mapping[str, tuple[OperationInterface, ...]] = field(default_factory=_no_steps)
    skipped: Mapping[str, tuple[str, ...]] = field(default_factory=_no_targets)
    states: Mapping[str, BundleState] = field(default_factory=_no_states)
    lock: RecipeLock = field(default_factory=RecipeLock)
    listed: frozenset[str] = frozenset()

    def sections(self) -> tuple[OperationInterface, ...]:
        """Return one block of steps per package: undone first, then applied, then skipped."""
        return (*self._undo(), *self._apply(), *self._skip())

    def next_lock(self) -> RecipeLock:
        """Return the lock this sync would leave behind.

        An untouched package keeps everything but its bundle standings, which
        are recomputed: another package arriving or leaving changes what
        requires what, and the lock is where that is read back from.
        """
        entries = dict(self.lock.entries)
        for name in self.selection.unconfigure:
            _ = entries.pop(name, None)
        for name in (*self.selection.configure, *self.selection.update):
            planned = self.planned[name]
            entries[name] = LockEntry(
                recipe=self.installed[name].recipe_hash,
                bundles=self._locked_states(name),
                files=planned.files,
                env=planned.env,
                gitignore=planned.gitignore,
            )
        for name in self.selection.unchanged:
            entries[name] = replace(entries[name], bundles=self._locked_states(name))
        return RecipeLock(entries)

    def _undo(self) -> tuple[OperationInterface, ...]:
        """Report and undo every package the lock has and the project no longer does."""
        steps: list[OperationInterface] = []
        for name in self.selection.unconfigure:
            steps.append(Section("unconfigure", name))
            steps.extend(self.undone[name])
            steps.extend(
                BundleNote(_class_name(target), "removed")
                for target in self.lock.entries[name].bundles
                if target in self.listed
            )
        return tuple(steps)

    def _apply(self) -> tuple[OperationInterface, ...]:
        """Report and apply every package the sync configures or re-applies."""
        groups = (
            ("configure", self.selection.configure),
            ("update", self.selection.update),
        )
        steps: list[OperationInterface] = []
        for action, names in groups:
            for name in names:
                planned = self.planned[name]
                steps.append(Section(action, name))
                steps.extend(planned.operations)
                steps.extend(
                    BundleNote(_class_name(target), _STATE_NOTES[self.states[target]])
                    for target in self.installed[name].config.bundles
                    if target in self.states
                )
                if planned.notes is not None:
                    steps.append(planned.notes)
        return tuple(steps)

    def _skip(self) -> tuple[OperationInterface, ...]:
        """Report every package whose bundle class the installation does not carry."""
        steps: list[OperationInterface] = []
        for name, targets in self.skipped.items():
            steps.append(Section("skip", name))
            steps.extend(
                BundleNote(_class_name(target), f"skipped: install {name}[di]")
                for target in targets
            )
        return tuple(steps)

    def _locked_states(self, name: str) -> dict[str, BundleState]:
        """Return one package's bundles mapped to the standing this sync gave them."""
        prior = self.lock.entries.get(name)
        recorded: Mapping[str, BundleState] = prior.bundles if prior is not None else {}
        return {
            target: _settled(self.states[target], recorded.get(target))
            for target in self.installed[name].config.bundles
            if target in self.states
        }


def _class_name(target: str) -> str:
    """Return the bundle class's own name out of a ``"module:Class"`` target."""
    return target.partition(":")[2]


def _settled(state: BundleState, recorded: BundleState | None) -> BundleState:
    """Keep a bundle this package once listed as listed, not read back as adopted.

    ``adopted`` means the bundle was in the application's list before any
    recipe ran, and it is the one standing the list alone can no longer tell
    apart once a sync has added the bundle itself. The lock still knows, and a
    sync that re-read it as adopted would rewrite the lock every time.
    """
    if state == "adopted" and recorded == "listed":
        return "listed"
    return state
