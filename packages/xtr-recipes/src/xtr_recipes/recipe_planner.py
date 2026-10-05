"""RecipePlanner: turning one recipe into the steps that apply or undo it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from .operation.delete_file import DeleteFile
from .operation.keep_file import KeepFile
from .operation.move_file import MoveFile
from .operation.notes import Notes
from .operation.put_block import PutBlock
from .operation.remove_block import RemoveBlock
from .operation.write_file import WriteFile
from .operation.write_new_file import WriteNewFile
from .planned_recipe import PlannedRecipe
from .recipe_lock import LockedFile

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from pathlib import Path

    from .marked_block_editor import MarkedBlockEditor
    from .notes_config import NotesConfig
    from .operation.operation_interface import OperationInterface
    from .project import Project
    from .recipe_loader import Recipe
    from .recipe_lock import LockEntry

__all__ = ["RecipePlanner"]

_ENV = ".env"
_GITIGNORE = ".gitignore"
_CONFIG_PREFIX = "config/"
_CONFIG_INIT = "config/__init__.py"
_CONFIG_INIT_BODY = (
    '"""Configuration modules."""\n\nfrom __future__ import annotations\n\n'
    "__all__: list[str] = []\n"
)
_SCRIPT = "<script>"
# Appended to a file set aside on unconfigure: no import resolves to it.
_REMOVED = ".removed"


@final
@dataclass(frozen=True, slots=True)
class _Destination:
    """One file a recipe writes: where it goes, how it reads, what goes in it."""

    path: Path
    display: str
    content: str


@final
class RecipePlanner:
    """Plans one recipe at a time, reading the project but never writing to it.

    Everything it decides, it decides from what is on disk now: whether a file
    is absent, untouched since the lock recorded it, edited or adopted, and
    whether a shared block would come out any different. Nothing is applied
    here, so a plan can be printed and thrown away.

    One planner serves one plan run: it remembers whether the application's
    ``config`` package has already been accounted for, so two recipes writing
    into it do not both claim to create its ``__init__.py``. Build a fresh one
    per run.
    """

    __slots__ = ("_config_init_planned", "_editor", "_project")

    def __init__(self, project: Project, editor: MarkedBlockEditor) -> None:
        """Plan for ``project``, reading its shared blocks through ``editor``."""
        self._project = project
        self._editor = editor
        self._config_init_planned = False

    def configure(self, recipe: Recipe) -> PlannedRecipe:
        """Plan a recipe the lock has never recorded.

        A file the project already has is adopted — kept as it is and locked
        as adopted, so removing the package later leaves it alone.
        """
        operations: list[OperationInterface] = []
        files: dict[str, LockedFile] = {}
        for destination, template in recipe.config.files.items():
            operations.extend(self._config_init(destination))
            target = self._target(recipe, destination, template)
            if target.path.is_file():
                operations.append(KeepFile(target.display, "adopted"))
                files[target.display] = LockedFile(_sha256(_read(target.path)), adopted=True)
            else:
                operations.append(WriteFile(target.path, target.display, target.content))
                files[target.display] = LockedFile(_sha256(target.content), adopted=False)
        return self._finish(recipe, tuple(operations), files)

    def update(self, recipe: Recipe, prior: LockEntry, force: bool) -> PlannedRecipe:
        """Plan a recipe whose content has moved on from what the lock recorded.

        Args:
            recipe: The recipe as it ships now.
            prior: What the lock says was applied last time.
            force: Whether to overwrite a file that is not the sync's to
                overwrite; without it the new content goes beside the file.

        Returns:
            The recipe's steps and what the lock should then say.
        """
        operations: list[OperationInterface] = []
        files: dict[str, LockedFile] = {}
        for destination, template in recipe.config.files.items():
            operations.extend(self._config_init(destination))
            target = self._target(recipe, destination, template)
            step, locked = self._reconcile(target, prior.files.get(target.display), force)
            if step is not None:
                operations.append(step)
            files[target.display] = locked
        operations.extend(self._dropped(prior, files))
        return self._finish(recipe, tuple(operations), files)

    def unconfigure(self, package: str, prior: LockEntry) -> tuple[OperationInterface, ...]:
        """Plan the undoing of a recipe whose package is gone.

        The lock alone says what to undo, which is the point of keeping it:
        every file it recorded as written and untouched goes, and the package's
        own blocks in the shared files are removed. An edited or adopted file
        still configures the package that is gone, so left where it is the
        application would fail to load it; it is the owner's, so it is not
        deleted either, but renamed out of the way with its content intact.
        """
        return (*self._dropped(prior, (), set_aside=True), *self._clear_blocks(package))

    def _target(self, recipe: Recipe, destination: str, template: str) -> _Destination:
        """Resolve one manifest entry against the project and render its template."""
        path = self._project.package_dir / destination
        return _Destination(
            path=path,
            display=self._display(path),
            content=recipe.render(template, app=self._project.app),
        )

    def _reconcile(
        self,
        target: _Destination,
        prior: LockedFile | None,
        force: bool,
    ) -> tuple[OperationInterface | None, LockedFile]:
        """Decide what becomes of one file a re-applied recipe still declares."""
        if not target.path.is_file():
            return (
                WriteFile(target.path, target.display, target.content),
                LockedFile(_sha256(target.content), adopted=False),
            )
        current = _read(target.path)
        written = LockedFile(_sha256(target.content), adopted=False)
        if prior is not None and not prior.adopted and _sha256(current) == prior.sha256:
            step = None if current == target.content else WriteFile(*_parts(target))
            return step, written
        if force:
            return WriteFile(*_parts(target)), written
        if prior is None:
            # A destination the manifest has only just added, already in the
            # project: adopted, exactly as a first configure would.
            return KeepFile(target.display, "adopted"), LockedFile(_sha256(current), adopted=True)
        kept = prior
        # A file that already reads as the recipe renders it has nothing to
        # reconcile; offering one anyway would leave a `.new` copy beside every
        # adopted file, on every release.
        step = None if current == target.content else WriteNewFile(*_parts(target))
        return step, kept

    def _dropped(
        self,
        prior: LockEntry,
        kept: Collection[str],
        *,
        set_aside: bool = False,
    ) -> tuple[OperationInterface, ...]:
        """Plan what becomes of the locked files a recipe no longer declares.

        An untouched file is deleted. An edited or adopted one is kept where it
        is while the package stays installed, and set aside when it is gone.
        """
        steps: list[OperationInterface] = []
        for display, locked in prior.files.items():
            path = self._project.project_dir / display
            if display in kept or not path.is_file():
                continue
            if not locked.adopted and _sha256(_read(path)) == locked.sha256:
                steps.append(DeleteFile(path, display))
                continue
            reason = "adopted" if locked.adopted else "edited"
            if set_aside:
                target = _free_name(path)
                steps.append(MoveFile(path, display, target, self._display(target), reason))
            else:
                steps.append(KeepFile(display, reason))
        return tuple(steps)

    def _config_init(self, destination: str) -> tuple[OperationInterface, ...]:
        """Plan the application's ``config`` package, once, before the first file in it.

        A destination under ``config/`` needs the package to import from. It is
        created when missing and adopted when present, never locked and never
        deleted: several recipes write into it, and it outlives all of them.
        """
        if self._config_init_planned or not destination.startswith(_CONFIG_PREFIX):
            return ()
        self._config_init_planned = True
        path = self._project.package_dir / _CONFIG_INIT
        if path.is_file():
            return ()
        return (WriteFile(path, self._display(path), _CONFIG_INIT_BODY),)

    def _finish(
        self,
        recipe: Recipe,
        operations: tuple[OperationInterface, ...],
        files: Mapping[str, LockedFile],
    ) -> PlannedRecipe:
        """Add the shared blocks and the notes to a recipe's file steps."""
        env_step, env = self._env(recipe)
        ignore_step, gitignore = self._gitignore(recipe)
        blocks = tuple(step for step in (env_step, ignore_step) if step is not None)
        return PlannedRecipe(
            operations=operations + blocks,
            notes=self._notes(recipe.config.notes),
            files=files,
            env=env,
            gitignore=gitignore,
        )

    def _env(self, recipe: Recipe) -> tuple[OperationInterface | None, tuple[str, ...]]:
        """Plan the recipe's ``.env`` block, and name the keys it would hold."""
        path = self._project.project_dir / _ENV
        text = self._editor.read(path)
        package = recipe.distribution
        lines = self._editor.env_lines(text, package, recipe.config.env)
        keys = self._editor.env_keys(text, package, recipe.config.env)
        return self._block(path, _ENV, text, lines, package), keys

    def _gitignore(self, recipe: Recipe) -> tuple[OperationInterface | None, tuple[str, ...]]:
        """Plan the recipe's ``.gitignore`` block, and name the lines it would hold."""
        path = self._project.project_dir / _GITIGNORE
        text = self._editor.read(path)
        package = recipe.distribution
        lines = self._editor.ignore_lines(text, package, recipe.config.gitignore)
        return self._block(path, _GITIGNORE, text, lines, package), lines

    def _block(
        self,
        path: Path,
        display: str,
        text: str,
        lines: tuple[str, ...],
        package: str,
    ) -> OperationInterface | None:
        """Return the step that would change the file, or ``None`` when none would.

        Contributing no lines is the same as having no block, so a recipe that
        stops contributing clears the block it once wrote.
        """
        if self._editor.put_block(text, package, lines) == text:
            return None
        if lines:
            return PutBlock(path, display, package, lines)
        return RemoveBlock(path, display, package)

    def _clear_blocks(self, package: str) -> tuple[OperationInterface, ...]:
        """Plan the removal of the package's blocks from the shared files."""
        steps: list[OperationInterface] = []
        for display in (_ENV, _GITIGNORE):
            path = self._project.project_dir / display
            text = self._editor.read(path)
            if self._editor.remove_block(text, package) != text:
                steps.append(RemoveBlock(path, display, package))
        return tuple(steps)

    def _notes(self, config: NotesConfig) -> Notes | None:
        """Return the recipe's notes with ``<script>`` resolved, or ``None`` when empty."""
        script = self._project.script
        notes = Notes(
            steps=_scripted(config.steps, script),
            check=_scripted(config.check, script),
            run=_scripted(config.run, script),
        )
        if not (notes.steps or notes.check or notes.run):
            return None
        return notes

    def _display(self, path: Path) -> str:
        """Return ``path`` as the plan and the lock spell it: relative, ``/``-separated."""
        return path.relative_to(self._project.project_dir).as_posix()


def _parts(target: _Destination) -> tuple[Path, str, str]:
    """Return the destination as the arguments a file-writing step takes."""
    return target.path, target.display, target.content


def _read(path: Path) -> str:
    """Return a file's text."""
    return path.read_text(encoding="utf-8")


def _free_name(path: Path) -> Path:
    """Return ``<file>.removed``, numbered when an earlier one is already there."""
    target = path.with_name(f"{path.name}{_REMOVED}")
    number = 0
    while target.exists():
        number += 1
        target = path.with_name(f"{path.name}{_REMOVED}.{number}")
    return target


def _sha256(text: str) -> str:
    """Return the hash the lock records for a file's content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scripted(lines: Sequence[str], script: str | None) -> tuple[str, ...]:
    """Return ``lines`` with ``<script>`` replaced by the application's own command.

    An application with no declared script leaves the placeholder standing:
    whoever reads the note knows what their own entry point is called.
    """
    if script is None:
        return tuple(lines)
    return tuple(line.replace(_SCRIPT, script) for line in lines)
