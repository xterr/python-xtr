"""Synchronizer: the difference between what is installed and what was applied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from .bundle_planner import BundlePlanner
from .bundle_requirements import BundleRequirements
from .bundles_file import BundlesFile
from .exception import RecipeNotInstalledError
from .marked_block_editor import MarkedBlockEditor
from .normalise import normalise
from .operation.delete_project_file import DeleteProjectFile
from .operation.plan import Plan
from .operation.write_bundles import WriteBundles
from .operation.write_lock import WriteLock
from .recipe_loader import RecipeLoader
from .recipe_lock import LOCK_NAME, RecipeLock
from .recipe_planner import RecipePlanner
from .recipe_survey import RecipeSurvey
from .sync_draft import SyncDraft
from .sync_options import SyncOptions
from .sync_selection import SyncSelection

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from .operation.operation_interface import OperationInterface
    from .planned_recipe import PlannedRecipe
    from .project import Project
    from .recipe_loader import Recipe
    from .recipe_source_interface import RecipeSourceInterface

__all__ = ["Synchronizer"]

_BUNDLES_NAME = "bundles.py"
_SRC = "src"


@final
@dataclass(frozen=True, slots=True)
class _Current:
    """What the project and the installed recipes say before anything is planned."""

    bundles: BundlesFile
    bundles_text: str | None
    lock: RecipeLock
    lock_text: str | None
    installed: Mapping[str, Recipe]
    unloadable: Mapping[str, tuple[str, ...]]


@final
class Synchronizer:
    """Brings a project in line with the recipes of its direct dependencies.

    The work is a diff: what is installed against what the lock records.
    Nothing cares how a package arrived or left, so the same run configures
    what is new, re-applies what has changed, undoes what is gone, and finds
    nothing to do the second time.

    Planning and applying are separate on purpose. :meth:`plan` only reads, so
    a command can print the steps or refuse a project that would change;
    :meth:`apply` carries out a plan already computed.
    """

    __slots__ = ("_loader", "_project", "_requirements")

    def __init__(
        self,
        project: Project,
        source: RecipeSourceInterface | None = None,
        requirements: BundleRequirements | None = None,
    ) -> None:
        """Sync ``project`` from ``source``, resolving bundles with ``requirements``."""
        self._project = project
        self._loader = RecipeLoader(source)
        self._requirements = requirements if requirements is not None else BundleRequirements()

    def plan(self, options: SyncOptions | None = None) -> Plan:
        """Compute every step the sync would take, writing nothing.

        Args:
            options: How to run; the default syncs everything and overwrites
                nothing the sync does not own.

        Returns:
            The plan, in the order it reads and applies.

        Raises:
            BundlesNotEditableError: The application's bundle list is shaped in
                a way it cannot be rewritten from. Raised before any step is
                computed, so a project that cannot be finished is not half-done.
            RecipeNotInstalledError: One package was named and it has no recipe
                to apply.
        """
        chosen = options if options is not None else SyncOptions()
        current = self._read()
        selection, skipped = self._select(chosen.only, current)
        planner = RecipePlanner(self._project, MarkedBlockEditor())
        planned: dict[str, PlannedRecipe] = {
            name: planner.configure(current.installed[name]) for name in selection.configure
        }
        for name in selection.update:
            prior = current.lock.entries[name]
            planned[name] = planner.update(current.installed[name], prior, chosen.force)
        bundles, states = BundlePlanner(self._requirements).finalize(
            current.bundles,
            self._removed(selection, current),
            self._candidates(selection, current),
            _recorded_required(current) if current.unloadable else (),
        )
        draft = SyncDraft(
            selection=selection,
            installed=current.installed,
            planned=planned,
            undone={
                name: planner.unconfigure(name, current.lock.entries[name])
                for name in selection.unconfigure
            },
            skipped=skipped,
            states=states,
            lock=current.lock,
            listed=frozenset(entry.target for entry in current.bundles.entries),
        )
        return Plan(
            operations=draft.sections(),
            project_operations=self._write_steps(draft, current, bundles),
            previous_lock=current.lock,
        )

    def apply(self, plan: Plan) -> None:
        """Carry out a plan :meth:`plan` computed."""
        plan.apply()

    def survey(self) -> RecipeSurvey:
        """Report what is installed and where each recipe stands, planning nothing.

        Reads exactly what :meth:`plan` reads and stops there, so a command
        that only tells the application owner what is configured agrees with
        the one that configures it.

        Returns:
            Each installed recipe, each package skipped for want of its
            bundle class, and where the lock leaves them.

        Raises:
            BundlesNotEditableError: The application's bundle list is shaped
                in a way it cannot be rewritten from.
        """
        current = self._read()
        return RecipeSurvey(
            installed=current.installed,
            skipped=current.unloadable,
            selection=SyncSelection.diff(current.installed, current.lock, current.unloadable),
            lock=current.lock,
        )

    def _read(self) -> _Current:
        """Read the bundle list, the lock and the installed recipes.

        The bundle list comes first and is read in full: a file that cannot be
        rewritten must stop the sync before it writes anything else.
        """
        bundles_path = self._project.package_dir / _BUNDLES_NAME
        bundles = BundlesFile.read(bundles_path)
        installed: dict[str, Recipe] = {}
        unloadable: dict[str, tuple[str, ...]] = {}
        for recipe in self._loader.load():
            if recipe.distribution not in self._project.dependencies:
                continue
            absent = tuple(
                target
                for target in recipe.config.bundles
                if not self._requirements.loadable(target, recipe.distribution)
            )
            if absent:
                unloadable[recipe.distribution] = absent
            else:
                installed[recipe.distribution] = recipe
        return _Current(
            bundles=bundles,
            bundles_text=_text(bundles_path),
            lock=RecipeLock.load(self._project.project_dir),
            lock_text=_text(self._project.project_dir / LOCK_NAME),
            installed=installed,
            unloadable=unloadable,
        )

    def _select(
        self,
        only: str | None,
        current: _Current,
    ) -> tuple[SyncSelection, Mapping[str, tuple[str, ...]]]:
        """Choose what the run acts on, and which packages it only reports as skipped."""
        if only is None:
            selection = SyncSelection.diff(current.installed, current.lock, current.unloadable)
            return selection, current.unloadable
        package = normalise(only)
        if package in current.unloadable:
            return SyncSelection(), {package: current.unloadable[package]}
        if package not in current.installed:
            raise RecipeNotInstalledError(package)
        return SyncSelection.only(package, current.lock), {}

    def _removed(self, selection: SyncSelection, current: _Current) -> set[str]:
        """Return the bundle targets to take out of the application's list."""
        removed: set[str] = set()
        for name in selection.unconfigure:
            removed.update(current.lock.entries[name].bundles)
        for name in selection.update:
            prior = current.lock.entries[name]
            removed.update(set(prior.bundles) - set(current.installed[name].config.bundles))
        return removed

    def _candidates(
        self,
        selection: SyncSelection,
        current: _Current,
    ) -> dict[str, Mapping[str, bool]]:
        """Return every bundle the run puts forward, mapped to its environments.

        A full sync names the bundles of every installed recipe, untouched ones
        included: whether a bundle is left out because something else requires
        it depends on the whole list, so it is decided afresh each time rather
        than carried over from the lock.
        """
        candidates: dict[str, Mapping[str, bool]] = {}
        for name in (*selection.configure, *selection.update, *selection.unchanged):
            candidates.update(current.installed[name].config.bundles)
        return candidates

    def _write_steps(
        self,
        draft: SyncDraft,
        current: _Current,
        bundles: BundlesFile,
    ) -> tuple[OperationInterface, ...]:
        """Return the two whole-project writes, each only when it would change something.

        A file that would come out empty — no bundle left to list, no recipe
        left to lock — is deleted rather than written blank, so unconfiguring
        the last package leaves the project as it was before the first.
        """
        steps: list[OperationInterface] = []
        bundles_path = self._project.package_dir / _BUNDLES_NAME
        bundles_display = bundles_path.relative_to(self._project.project_dir).as_posix()
        rendered = bundles.render(self._first_party())
        if bundles.entries:
            if _replaces(rendered, current.bundles_text, has_entries=True):
                steps.append(WriteBundles(bundles_path, bundles_display, rendered))
        elif current.bundles_text is not None:
            steps.append(DeleteProjectFile(bundles_path, bundles_display))
        lock = draft.next_lock()
        if lock.entries:
            if _replaces(lock.dumps(), current.lock_text, has_entries=True):
                steps.append(WriteLock(lock, self._project.project_dir))
        elif current.lock_text is not None:
            steps.append(DeleteProjectFile(self._project.project_dir / LOCK_NAME, LOCK_NAME))
        return tuple(steps)

    def _first_party(self) -> frozenset[str]:
        """Return the application's own top-level packages, for the import order.

        Under a ``src`` layout every package beside the application is its own
        too, so an entry importing from one of them is sorted with the
        application's imports rather than with the dependencies'.
        """
        parent = self._project.package_dir.parent
        if parent.name != _SRC:
            return frozenset({self._project.app})
        beside = (
            child.name
            for child in parent.iterdir()
            if child.is_dir() and (child / "__init__.py").is_file()
        )
        return frozenset({self._project.app, *(name for name in beside if name.isidentifier())})


def _recorded_required(current: _Current) -> frozenset[str]:
    """Return every bundle target the lock records as left out for being required."""
    return frozenset(
        target
        for entry in current.lock.entries.values()
        for target, state in entry.bundles.items()
        if state == "required"
    )


def _text(path: Path) -> str | None:
    """Return a file's text, or ``None`` when there is no such file."""
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _replaces(rendered: str, text: str | None, *, has_entries: bool) -> bool:
    """Whether a generated file should replace, or first create, what is on disk.

    A project with no such file and nothing to put in it needs none: an
    application wiring nothing is not made to carry an empty bundle list, and
    one with no recipes applied is not given an empty lock.
    """
    if text is None:
        return has_entries
    return rendered != text
