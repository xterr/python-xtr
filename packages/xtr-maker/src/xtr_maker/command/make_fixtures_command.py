"""``make:fixtures``: a fixture class seeding the application's database."""

from __future__ import annotations

from typing import Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import (  # noqa: TC002 — the console reads annotations at runtime.
    Injected,
)

from xtr_maker.class_name import ClassName
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.
from xtr_maker.import_collector import ImportCollector

__all__ = ["MakeFixturesCommand"]

_DEFAULT_NAME: Final = "AppFixtures"
"""The name offered when asked: a first fixture class, before there are several."""

_ATTEMPTS: Final = 3
"""How many times the name is asked: an input that has ended answers empty every time."""

_TEMPLATE: Final = "fixtures/fixtures.py.jinja"


@final
@as_command("make:fixtures", description="Write a fixture class that seeds the database.")
class MakeFixturesCommand:
    """Writes ``fixtures/<name>.py``: a fixture class with an empty ``load``.

    The fixtures bundle finds it wherever it is, so the folder is only where
    makers put it; ``catalog.BookFixtures`` writes ``fixtures/catalog/``. The
    name is asked when left out, ``AppFixtures`` offered; without a terminal
    (``-n``) it must be given.
    """

    __slots__ = ("_file_manager",)

    def __init__(self, file_manager: FileManager) -> None:
        """Write into the package ``file_manager`` holds.

        Args:
            file_manager: The application package the class is written into.
        """
        self._file_manager = file_manager

    async def __call__(
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
    ) -> int:
        """Write a fixture class.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the file.
            name: The fixture's class name, such as ``AppFixtures`` or ``books``;
                ``catalog.BookFixtures`` writes it under ``fixtures/catalog/``.
        """
        try:
            fixture = self._fixture_name(io, name)
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        try:
            path = generator.generate_class(fixture, _TEMPLATE, _context(fixture, generator))
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(f"Wrote {fixture.short_name}.")
        io.text("Next:")
        io.text(
            f"  - Open {escape(self._file_manager.relative(path))} and add the objects it seeds."
        )
        io.text("  - Load them with orm:fixtures:load.")
        return ExitCode.SUCCESS

    def _fixture_name(self, io: ConsoleStyle, typed: str | None) -> ClassName:
        """Return the fixture class ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be asked.
            InvalidClassNameError: When the name given cannot name a class, or
                no answer could after the last attempt.
        """
        if typed is not None:
            return self._fixture_class(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the fixture class to write: make:fixtures <name>, such as"
                " make:fixtures AppFixtures."
            )
        question = "The fixture's class name"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._fixture_class(io.ask(question, _DEFAULT_NAME))
            except InvalidClassNameError as error:
                io.error(escape(str(error)))
        return self._fixture_class(io.ask(question, _DEFAULT_NAME))

    def _fixture_class(self, typed: str) -> ClassName:
        return ClassName.create(
            typed, root_package=self._file_manager.root_package, kind="fixtures", suffix="Fixtures"
        )


def _context(fixture: ClassName, generator: Generator) -> dict[str, object]:
    """Return what the template reads: its imports, and the names it writes them under."""
    imports = ImportCollector(fixture.root_package)
    if generator.final_classes:
        _ = imports.add("typing", "final")
    override = imports.add("typing", "override")
    session = imports.add("sqlalchemy.ext.asyncio", "AsyncSession", type_checking=True)
    base = imports.add("xtr_orm_fixtures", "Fixture")
    return {"imports": imports.render(), "override": override, "session": session, "base": base}
