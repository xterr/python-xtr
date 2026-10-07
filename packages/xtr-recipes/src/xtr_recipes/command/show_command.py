"""``recipes:show``: what is installed, where it stands, and what one recipe declares."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — the console reads annotations at runtime.
from typing import TYPE_CHECKING, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from xtr_recipes import command_support
from xtr_recipes.exception import RecipeNotInstalledError, RecipesError
from xtr_recipes.operation.notes import Notes

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_recipes.recipe_lock import LockEntry
    from xtr_recipes.recipe_survey import RecipeSurvey

__all__ = ["ShowCommand"]

_NONE_INSTALLED = "no recipes installed"
_LOCKED = "locked"
_NOT_CONFIGURED = "not configured"
_OUTDATED = "outdated"
_REMOVED = "removed"
_ARROW = "←"


@as_command("recipes:show")
@final
class ShowCommand:
    """List the project's recipes and their standing, or read one of them.

    Writes nothing. Named without a package it answers "what is configured
    here, and what would a sync have to do?"; named with one it answers "what
    does this package's recipe actually declare?" — the bundles, the files,
    the environment keys, the ignore lines and the notes, as the recipe ships
    them.
    """

    async def __call__(
        self,
        io: ConsoleStyle,
        package: str | None = None,
        *,
        project_dir: Path | None = None,
    ) -> int:
        """Report the project's recipes, or one of them in full.

        Args:
            io: Where the report is written.
            package: The distribution to read; every one of them when left
                out.
            project_dir: The project to read; the nearest one at or above the
                current directory by default.
        """
        try:
            survey = command_support.build_synchronizer(
                command_support.load_project(project_dir)
            ).survey()
            if package is None:
                _listing(io, survey)
            else:
                _detail(io, survey, command_support.normalise(package))
        except RecipesError as error:
            return command_support.failed(io, error)
        return ExitCode.SUCCESS


def _listing(io: ConsoleStyle, survey: RecipeSurvey) -> None:
    """Print one row per package the project has anything to say about."""
    states = _states(survey)
    if not states:
        io.text(_NONE_INSTALLED)
        return
    io.table(
        ("Package", "State"),
        tuple((escape(name), escape(state)) for name, state in states.items()),
    )


def _detail(io: ConsoleStyle, survey: RecipeSurvey, package: str) -> None:
    """Print everything one recipe declares, as its manifest declares it.

    Args:
        io: Where the recipe is written.
        survey: The project's recipes, read once.
        package: The distribution to read, normalised.

    A package the project no longer installs but the lock still records — one
    removed from the dependencies but not yet synced away — is read from the
    lock instead, so its standing can still be inspected before a sync undoes
    it.

    Raises:
        RecipeNotInstalledError: Neither an installed recipe nor a lock entry
            belongs to ``package``.
    """
    recipe = survey.installed.get(package)
    if recipe is None:
        entry = survey.lock.entries.get(package)
        if entry is None:
            raise RecipeNotInstalledError(package)
        _detail_from_lock(io, package, entry)
        return
    config = recipe.config
    notes = config.notes
    io.section(escape(package))
    command_support.write(
        io,
        (
            *_group("bundles", [_bundle(*entry) for entry in config.bundles.items()]),
            *_group("files", [f"{into} {_ARROW} {out}" for into, out in config.files.items()]),
            *_group("env", list(config.env)),
            *_group("gitignore", config.gitignore),
            *Notes(steps=notes.steps, check=notes.check, run=notes.run).render(),
        ),
    )


def _detail_from_lock(io: ConsoleStyle, package: str, entry: LockEntry) -> None:
    """Print what the lock records for a package the project no longer installs."""
    io.section(escape(package))
    command_support.write(
        io,
        (
            *_group("bundles", [f"{target} ({state})" for target, state in entry.bundles.items()]),
            *_group("files", list(entry.files)),
            *_group("env", list(entry.env)),
            *_group("gitignore", list(entry.gitignore)),
        ),
    )


def _states(survey: RecipeSurvey) -> dict[str, str]:
    """Map every package the project has something to say about to its standing.

    A package installed without the extra that ships its bundle class is also
    a locked package that is no longer applicable, so it would read as
    *removed*; it is overwritten last because naming the extra is the answer
    that gets it configured again.
    """
    selection = survey.selection
    states = dict.fromkeys(selection.unchanged, _LOCKED)
    states.update(dict.fromkeys(selection.configure, _NOT_CONFIGURED))
    states.update(dict.fromkeys(selection.update, _OUTDATED))
    states.update(dict.fromkeys(selection.unconfigure, _REMOVED))
    states.update({name: f"skipped: install {name}[di]" for name in survey.skipped})
    return dict(sorted(states.items()))


def _group(label: str, items: Sequence[str]) -> tuple[str, ...]:
    """Return one labelled block of lines, or none when the recipe declares none."""
    if not items:
        return ()
    return (f"  {label}:", *(f"    - {item}" for item in items))


def _bundle(target: str, flags: Mapping[str, bool]) -> str:
    """Return one bundle entry as the application's bundle list spells it."""
    rendered = ", ".join(f"{name}={str(active).lower()}" for name, active in flags.items())
    return f"{target} {rendered}" if rendered else target
