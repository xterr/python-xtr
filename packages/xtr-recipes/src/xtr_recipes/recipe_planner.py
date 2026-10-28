"""RecipePlanner: turning one recipe into the steps that apply or undo it."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from .compose_file_editor import ComposeFileEditor
from .operation.delete_file import DeleteFile
from .operation.keep_file import KeepFile
from .operation.mint_key import MintKey
from .operation.move_file import MoveFile
from .operation.notes import Notes
from .operation.put_block import PutBlock
from .operation.put_compose_blocks import PutComposeBlocks
from .operation.remove_block import RemoveBlock
from .operation.write_file import WriteFile
from .operation.write_new_file import WriteNewFile
from .planned_recipe import PlannedRecipe
from .recipe_config import COMPOSE_FILES
from .recipe_lock import LockedFile
from .safe_path import within

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from pathlib import Path

    from .marked_block_editor import MarkedBlockEditor
    from .notes_config import NotesConfig
    from .operation.operation_interface import OperationInterface
    from .project import Project
    from .recipe_config import RecipeConfig
    from .recipe_loader import Recipe
    from .recipe_lock import LockEntry

__all__ = ["RecipePlanner"]

_ENV = ".env"
_GITIGNORE = ".gitignore"
_COMPOSE = ComposeFileEditor()
_CONFIG_DIR = "config"
# Where a package's configuration module goes, and where an earlier layout put
# it: one is read off the other by dropping this segment.
_PACKAGES_DIR = "config/packages/"
_INIT = "__init__.py"
_INIT_BODY = '"""{title}"""\n\nfrom __future__ import annotations\n\n__all__: list[str] = []\n'
_SCRIPT = "<script>"
# Appended to a file set aside on unconfigure: no import resolves to it.
_REMOVED = ".removed"
# Why a key already on disk is not minted again.
_KEY_IN_PLACE = "in place"
# Why a recipe-written file is moved from the earlier layout to the current one.
_RELOCATED = "relocated"
# Why a file in the earlier layout the recipe did not write is left there.
_ADOPTED = "adopted"


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

    One planner serves one plan run: it remembers which of the application's
    ``config`` packages have already been accounted for, so two recipes writing
    into one do not both claim to create its ``__init__.py``. Build a fresh one
    per run.
    """

    __slots__ = ("_config_packages_planned", "_editor", "_project")

    def __init__(self, project: Project, editor: MarkedBlockEditor) -> None:
        """Plan for ``project``, reading its shared blocks through ``editor``."""
        self._project = project
        self._editor = editor
        self._config_packages_planned: set[str] = set()

    def configure(self, recipe: Recipe) -> PlannedRecipe:
        """Plan a recipe the lock has never recorded.

        A file the project already has is adopted — kept as it is and locked
        as adopted, so removing the package later leaves it alone. So is one
        at the place an earlier layout put it, ``config/<name>.py`` for
        ``config/packages/<name>.py``: it already configures the package, and
        a second copy beside it would configure it twice.
        """
        operations: list[OperationInterface] = []
        files: dict[str, LockedFile] = {}
        for destination, template in recipe.config.files.items():
            operations.extend(self._config_init(destination))
            target = self._target(recipe, destination, template)
            earlier = self._earlier(destination)
            if target.path.is_file():
                operations.append(KeepFile(target.display, _ADOPTED))
                files[target.display] = LockedFile(_sha256(_read(target.path)), adopted=True)
            elif earlier is not None:
                path, display = earlier
                operations.append(KeepFile(display, _ADOPTED))
                files[display] = LockedFile(_sha256(_read(path)), adopted=True)
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

        A file the lock recorded at the place an earlier layout put it is
        carried to where the recipe writes it now when the recipe wrote it, and
        reconciled there as if it had always been; one the recipe adopted stays
        where it is, the owner's as before.
        """
        operations: list[OperationInterface] = []
        files: dict[str, LockedFile] = {}
        carried: set[str] = set()
        for destination, template in recipe.config.files.items():
            operations.extend(self._config_init(destination))
            target = self._target(recipe, destination, template)
            earlier = None if target.path.is_file() else self._earlier(destination)
            if earlier is not None:
                path, display = earlier
                carried.add(display)
                was = prior.files.get(display)
                if was is None or was.adopted:
                    operations.append(KeepFile(display, _ADOPTED))
                    files[display] = was or LockedFile(_sha256(_read(path)), adopted=True)
                    continue
                operations.append(MoveFile(path, display, target.path, target.display, _RELOCATED))
                step, locked = self._reconcile(target, was, force, _read(path))
            else:
                step, locked = self._reconcile(target, prior.files.get(target.display), force)
            if step is not None:
                operations.append(step)
            files[target.display] = locked
        operations.extend(self._dropped(prior, {*files, *carried}))
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
        return (
            *self._dropped(prior, (), set_aside=True),
            *self._clear_blocks(package),
            *self._compose(package, {}),
        )

    def _target(self, recipe: Recipe, destination: str, template: str) -> _Destination:
        """Resolve one manifest entry against the project and render its template."""
        package_rel = self._project.package_dir.relative_to(self._project.project_dir)
        display = (package_rel / destination).as_posix()
        # The manifest already refuses a traversing destination; this is the
        # backstop that no rendered file lands outside the project even so.
        _ = within(self._project.project_dir, display)
        path = self._project.package_dir / destination
        return _Destination(
            path=path,
            display=display,
            content=recipe.render(template, app=self._project.app),
        )

    def _earlier(self, destination: str) -> tuple[Path, str] | None:
        """Return where an earlier layout put ``destination``, when a file is there.

        A package's configuration module lived at ``config/<name>.py`` before it
        moved to ``config/packages/<name>.py``; nothing else has moved.
        """
        if not destination.startswith(_PACKAGES_DIR):
            return None
        path = self._project.package_dir / _CONFIG_DIR / destination.removeprefix(_PACKAGES_DIR)
        if not path.is_file():
            return None
        return path, self._display(path)

    def config_packages(self, destination: str) -> tuple[OperationInterface, ...]:
        """Plan every ``config`` package a file the run writes sits in, once each.

        The bundle list is written by the run as a whole rather than by a
        recipe, and it lives in ``config/`` too, so the run asks here for the
        packages a recipe's file would have been given.

        Args:
            destination: The file's path relative to the application package.
        """
        return self._config_init(destination)

    def _reconcile(
        self,
        target: _Destination,
        prior: LockedFile | None,
        force: bool,
        current: str | None = None,
    ) -> tuple[OperationInterface | None, LockedFile]:
        """Decide what becomes of one file a re-applied recipe still declares.

        ``current`` is the file's text when it is not at ``target`` yet — a file
        being carried there from an earlier layout — and is read from
        ``target`` otherwise.
        """
        if current is None:
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
        # adopted file, on every release. A `.new` copy that already holds this
        # exact content is nothing to write either, so a second sync is quiet.
        if current == target.content or _new_holds(target):
            step = None
        else:
            step = WriteNewFile(*_parts(target))
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
        """Plan every ``config`` package a destination sits in, once each, before the file.

        A destination under ``config/`` needs each package between ``config``
        and itself — ``config/routes/`` for a routes file — to be importable,
        and the kernel scans only packages. Each is created when missing and
        adopted when present, never locked and never deleted: several recipes
        write into it, and it outlives all of them.
        """
        directories = destination.split("/")[:-1]
        if not directories or directories[0] != _CONFIG_DIR:
            return ()
        operations: list[OperationInterface] = []
        for depth in range(1, len(directories) + 1):
            package = "/".join(directories[:depth])
            if package in self._config_packages_planned:
                continue
            self._config_packages_planned.add(package)
            path = self._project.package_dir / package / _INIT
            if path.is_file():
                continue
            title = "Configuration modules." if depth == 1 else f"Configuration modules: {package}."
            operations.append(WriteFile(path, self._display(path), _INIT_BODY.format(title=title)))
        return tuple(operations)

    def _finish(
        self,
        recipe: Recipe,
        operations: tuple[OperationInterface, ...],
        files: Mapping[str, LockedFile],
    ) -> PlannedRecipe:
        """Add the shared blocks, the keys and the notes to a recipe's file steps."""
        env_step, env, keys = self._env(recipe)
        ignore_step, gitignore = self._gitignore(recipe)
        blocks = tuple(step for step in (env_step, ignore_step) if step is not None)
        compose = self._compose(recipe.distribution, recipe.config.compose)
        return PlannedRecipe(
            operations=operations + blocks + compose + keys,
            notes=self._notes(recipe.config.notes),
            files=files,
            env=env,
            gitignore=gitignore,
        )

    def _env(
        self,
        recipe: Recipe,
    ) -> tuple[OperationInterface | None, tuple[str, ...], tuple[OperationInterface, ...]]:
        """Plan the recipe's ``.env`` block, the keys minted with it, and name its keys.

        Planned together because a minted key is encrypted with a secret the
        block holds: the key is sealed with exactly the value the application
        will read back, whether the sync generates it now or the block already
        has it.

        A key whose path variable the project already points at another file
        is the project's own: none is minted, and no pass phrase is made for it.
        """
        path = self._project.project_dir / _ENV
        text = self._editor.read(path)
        package = recipe.distribution
        config = recipe.config
        targets = {
            destination: within(self._project.project_dir, destination)
            for destination in config.keys
        }
        elsewhere = {
            destination
            for destination, key in config.keys.items()
            if key.path_env is not None
            and self._editor.env_value(text, key.path_env) not in {None, config.env[key.path_env]}
        }
        unminted = elsewhere | {name for name, target in targets.items() if target.exists()}
        entries = _env_defaults(config, unminted)
        lines = self._editor.env_lines(text, package, entries)
        keys = self._editor.env_keys(text, package, entries)
        written = self._editor.put_block(text, package, lines)
        return (
            self._block(path, _ENV, text, lines, package),
            keys,
            self._keys(config, targets, written, elsewhere),
        )

    def _keys(
        self,
        config: RecipeConfig,
        targets: Mapping[str, Path],
        env_text: str,
        elsewhere: Collection[str],
    ) -> tuple[OperationInterface, ...]:
        """Plan a mint for every declared key not on disk yet, and keep every one that is.

        Args:
            config: The recipe being planned.
            targets: Each declared key path mapped to where it lands.
            env_text: ``.env`` as it reads once the recipe's block is written,
                which is where each key's pass phrase is read from.
            elsewhere: The declared keys the project reads from another file,
                which are neither minted nor reported.
        """
        steps: list[OperationInterface] = []
        for destination, key in config.keys.items():
            if destination in elsewhere:
                continue
            target = targets[destination]
            if target.exists():
                steps.append(KeepFile(destination, _KEY_IN_PLACE))
                continue
            passphrase = (
                self._editor.env_value(env_text, key.passphrase)
                if key.passphrase is not None
                else None
            )
            steps.append(MintKey(target, destination, key.algorithm, passphrase))
        return tuple(steps)

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

    def _compose(
        self,
        package: str,
        compose: Mapping[str, Mapping[str, tuple[str, ...]]],
    ) -> tuple[OperationInterface, ...]:
        """Plan the package's blocks in each Compose file, clearing the ones it no longer writes.

        Nothing is lost by not recording them in the lock: the markers alone
        say which blocks are the package's, as they do in ``.env``.
        """
        steps: list[OperationInterface] = []
        for name in COMPOSE_FILES:
            sections = compose.get(name, {})
            path, display = self._compose_path(name)
            text = self._editor.read(path)
            if not sections and not _COMPOSE.has_blocks(text, package):
                continue
            if _COMPOSE.put_blocks(text, package, sections) != text:
                steps.append(PutComposeBlocks(path, display, package, sections))
        return tuple(steps)

    def _compose_path(self, name: str) -> tuple[Path, str]:
        """Return the Compose file the project keeps for ``name``, or ``name`` when it has none.

        Compose reads ``compose.yml`` and the older ``docker-compose.yaml`` and
        ``docker-compose.yml`` as well, so a project already keeping its
        services under one of those has them written there, not beside it.
        """
        base = name.removesuffix(".yaml")
        for candidate in (name, f"{base}.yml", f"docker-{base}.yaml", f"docker-{base}.yml"):
            path = within(self._project.project_dir, candidate)
            if path.is_file():
                return path, candidate
        return within(self._project.project_dir, name), name

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


def _new_holds(target: _Destination) -> bool:
    """Whether ``<path>.new`` already holds exactly the content a sync would write there."""
    new = target.path.parent / f"{target.path.name}.new"
    return new.is_file() and new.read_text(encoding="utf-8") == target.content


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


def _env_defaults(config: RecipeConfig, unminted: Collection[str]) -> dict[str, str]:
    """Return the recipe's ``[env]`` defaults with every generated secret made up.

    A pass phrase belongs to the key minted with it. A key this sync does not
    mint — one already on disk, one the project reads from elsewhere — is not
    encrypted with a secret it would make, so its pass phrase is offered with
    no default instead: a fresh one would not open the key that is used.

    Args:
        config: The recipe being planned.
        unminted: The declared keys this sync does not mint.
    """
    unsealed = {
        key.passphrase
        for destination, key in config.keys.items()
        if key.passphrase is not None and destination in unminted
    }
    defaults: dict[str, str] = {}
    for name, default in config.env.items():
        secret = config.secrets.get(name)
        if name in unsealed:
            defaults[name] = ""
        elif secret is not None:
            defaults[name] = secret.generate()
        else:
            defaults[name] = default
    return defaults


def _scripted(lines: Sequence[str], script: str | None) -> tuple[str, ...]:
    """Return ``lines`` with ``<script>`` replaced by the application's own command.

    An application with no declared script leaves the placeholder standing:
    whoever reads the note knows what their own entry point is called.
    """
    if script is None:
        return tuple(lines)
    return tuple(line.replace(_SCRIPT, script) for line in lines)
