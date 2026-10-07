"""Plan: everything a sync would do, computed before any of it is done."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, final

from xtr_recipes.recipe_lock import RecipeLock

from .section import Section
from .write_lock import WriteLock

if TYPE_CHECKING:
    from xtr_recipes.recipe_lock import LockEntry

    from .operation_interface import OperationInterface

__all__ = ["Plan"]


@final
@dataclass(frozen=True, slots=True)
class Plan:
    """The ordered steps of one sync, as data.

    Computing the whole plan before applying any of it is what makes printing
    it without doing it, and refusing a project that would change, the same
    code path as doing it: the steps are the single description both read.

    The steps come in two layers because a sync writes in two layers: each
    package's own, then the two files the whole run shares. Keeping them apart
    is what lets a run that stops part way say which packages it finished.

    Attributes:
        operations: Each package's steps, in the order they are reported and
            applied; every block opens with its heading.
        project_operations: The steps of the run as a whole — the bundle list
            and the lock — carried out once every package has had its say.
        previous_lock: The lock as the last sync left it, which a package this
            run does not finish keeps.
    """

    operations: tuple[OperationInterface, ...] = ()
    project_operations: tuple[OperationInterface, ...] = ()
    previous_lock: RecipeLock = field(default_factory=RecipeLock)

    @property
    def has_changes(self) -> bool:
        """Whether any step would touch the project.

        A plan can be made entirely of headings, kept files and bundle notes —
        there is something to say and nothing to do. That is the difference
        between a sync that reports and one that writes.
        """
        return any(operation.changes for operation in self._steps)

    def render(self) -> tuple[str, ...]:
        """Return every step's lines, in order."""
        return tuple(line for operation in self._steps for line in operation.render())

    def apply(self) -> None:
        """Carry out every step, in order.

        A run that stops part way leaves files on disk the lock knows nothing
        about, and the lock is the record a later sync reconciles against. So
        the lock is written before the failure propagates — for the packages
        whose every step ran and no others. One that stopped half way keeps the
        entry the last sync left it, so the next sync plans it again.
        """
        self._apply_packages()
        self._apply_project()

    @property
    def _steps(self) -> tuple[OperationInterface, ...]:
        """Return both layers' steps, in the order they are read and carried out."""
        return (*self.operations, *self.project_operations)

    def _apply_packages(self) -> None:
        """Carry out each package's steps, recording the ones that ran whole."""
        finished: list[str] = []
        current: str | None = None
        try:
            for operation in self.operations:
                if isinstance(operation, Section):
                    if current is not None:
                        finished.append(current)
                    current = operation.package
                operation.apply()
        except Exception as failure:
            self._record(frozenset(finished), failure)
            raise

    def _apply_project(self) -> None:
        """Carry out the steps of the run as a whole, which no one package owns.

        These write the files every package contributes to, so a failure here
        leaves none of them as a lock would claim: nothing is recorded, and the
        next sync plans the whole run again.
        """
        try:
            for operation in self.project_operations:
                operation.apply()
        except Exception as failure:
            self._record(frozenset(), failure)
            raise

    def _record(self, finished: frozenset[str], failure: BaseException) -> None:
        """Write the lock for ``finished`` alone, without standing in for ``failure``.

        The run already has a failure worth reporting, and a lock that cannot
        be written is not a better one: it is noted on the failure on its way
        out rather than raised over it. A plan with no lock step — unconfiguring
        the last package deletes the lock instead — leaves the committed one as
        it is, which is already the record of what is still configured.
        """
        step = self._lock_step
        if step is None:
            return
        partial = self._partial_lock(step.lock, finished)
        if partial.entries == self.previous_lock.entries:
            return
        try:
            replace(step, lock=partial).apply()
        except Exception as error:  # noqa: BLE001 — nothing here may displace ``failure``.
            failure.add_note(f"the lock was left as it was: {error}")

    @property
    def _lock_step(self) -> WriteLock | None:
        """Return the step that writes the lock, when this plan has one to write."""
        for operation in self.project_operations:
            if isinstance(operation, WriteLock):
                return operation
        return None

    def _partial_lock(self, complete: RecipeLock, finished: frozenset[str]) -> RecipeLock:
        """Return the lock as of ``finished``: their new entries, everyone else's old one."""
        entries: dict[str, LockEntry] = {}
        for name in dict.fromkeys((*self.previous_lock.entries, *complete.entries)):
            source = complete if name in finished else self.previous_lock
            entry = source.entries.get(name)
            if entry is not None:
                entries[name] = entry
        return RecipeLock(entries)
