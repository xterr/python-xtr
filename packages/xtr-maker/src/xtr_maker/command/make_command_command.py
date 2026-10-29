"""``make:command``: a console command class, its arguments and options declared."""

from __future__ import annotations

import re
from typing import Final, final

# CommandsLocator and ConsoleStyle are read at runtime too, by the container and the console.
from xtr_console import CommandsLocator, ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import (  # noqa: TC002 — the console reads annotations at runtime.
    Injected,
)

from xtr_maker.class_name import ClassName
from xtr_maker.command_parameter import LIST_TYPE, CommandParameter
from xtr_maker.command_source import CommandSource
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.

__all__ = ["MakeCommandCommand"]

_ATTEMPTS: Final = 3
"""How many times a value is asked: an input that has ended answers empty every time."""

_COMMAND_NAME: Final = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*(?::[A-Za-z0-9_][A-Za-z0-9_-]*)*")
"""A console name: words of letters, digits, '_' and '-', namespaces before ':'."""

_TEMPLATE: Final = "command/command.py.jinja"

_ARGUMENT_TYPES: Final = ("str", "int", "float", "list", "enum")
_OPTION_TYPES: Final = ("bool", "str", "int", "float", "list", "enum")
"""The types offered when asked; ``list`` stands for ``list[str]``, ``enum`` asks for the class."""

_DEMO: Final = (
    CommandParameter("name", "str", description="Name."),
    CommandParameter("yell", "bool", option=True, required=False, description="Yell."),
)
"""What a command declared without parameters takes: one argument and one option, to copy."""


@final
@as_command("make:command", description="Write a console command class.")
class MakeCommandCommand:
    """Writes ``command/<name>_command.py``: a class declared with ``@as_command``.

    The class is named after the last part of the console name —
    ``app:send-report`` is ``SendReportCommand`` — and its ``__call__`` takes
    the arguments, then after a bare ``*`` the options, each documented in its
    docstring, which is where ``--help`` reads them. Its body prints every
    value it was given, so the command runs as soon as it is written.

    Parameters come from ``--argument name[?][:type]`` and
    ``--option name[:type]``, each repeatable; without either, they are asked
    one by one. Without a terminal (``-n``) and without either, the command
    takes a ``name`` argument and a ``yell`` option to start from.
    """

    __slots__ = ("_commands", "_file_manager")

    def __init__(self, file_manager: FileManager, commands: CommandsLocator) -> None:
        """Write into the package ``file_manager`` holds, beside the commands ``commands`` holds.

        Args:
            file_manager: The application package the class is written into.
            commands: The application's commands; a name one of them answers
                to is refused.
        """
        self._file_manager = file_manager
        self._commands = commands

    async def __call__(
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        *,
        argument: list[str] | None = None,
        option: list[str] | None = None,
    ) -> int:
        """Write a console command class.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the file.
            name: The console name, such as ``app:send-report``.
            argument: An argument, as ``name[?][:type]``: ``?`` makes it
                optional; the type is ``str`` (the default), ``int``,
                ``float``, ``list`` or an enum class as ``module.Class``.
            option: An option, as ``name[:type]``: the type is ``bool`` (the
                default), ``str``, ``int``, ``float``, ``list`` or an enum class.
        """
        try:
            command_name = self._command_name(io, name)
            class_name = ClassName.create(
                command_name.rsplit(":", 1)[-1],
                root_package=self._file_manager.root_package,
                kind="command",
                suffix="Command",
            )
            description = _description(io, command_name)
            arguments, options = _parameters(io, argument or [], option or [])
            source = CommandSource(command_name, description, arguments, options)
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        context = source.context(class_name.root_package, final_classes=generator.final_classes)
        try:
            path = generator.generate_class(class_name, _TEMPLATE, context)
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(f"Wrote {class_name.short_name}.")
        io.text("Next:")
        io.text(f"  - Run {command_name} --help to see its arguments and options.")
        io.text(f"  - Open {escape(self._file_manager.relative(path))} and write what it does.")
        return ExitCode.SUCCESS

    def _command_name(self, io: ConsoleStyle, typed: str | None) -> str:
        """Return the console name ``typed``, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be
                asked, or the name cannot be used, after the last attempt.
            InvalidClassNameError: When its last part cannot name a class,
                after the last attempt.
        """
        if typed is not None:
            return self._checked(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the command to write: make:command <name>,"
                " such as make:command app:send-report."
            )
        question = "The command's name (such as [cyan]app:send-report[/])"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._checked(io.ask(question))
            except (InvalidArgumentError, InvalidClassNameError) as error:
                io.error(escape(str(error)))
        return self._checked(io.ask(question))

    def _checked(self, typed: str) -> str:
        """Return ``typed`` as a console name no command answers to yet.

        Raises:
            InvalidArgumentError: When it is not a console name, or is taken.
            InvalidClassNameError: When its last part cannot name a class.
        """
        name = typed.strip()
        if _COMMAND_NAME.fullmatch(name) is None:
            raise InvalidArgumentError(
                f"{name!r} cannot name a command: use letters, digits, '_' or '-',"
                " and ':' after a namespace, such as app:send-report."
            )
        taken = next((found for found in self._commands.commands() if name in found.names), None)
        if taken is not None:
            raise InvalidArgumentError(f"The command {taken.name!r} already answers to {name!r}.")
        _ = ClassName.create(
            name.rsplit(":", 1)[-1],
            root_package=self._file_manager.root_package,
            kind="command",
            suffix="Command",
        )
        return name


def _description(io: ConsoleStyle, command_name: str) -> str:
    """Return the summary ``--help`` shows; a blank answer keeps the placeholder."""
    return io.ask("What it does, shown by --help", f"Describe what {command_name} does.").strip()


def _parameters(
    io: ConsoleStyle, declared_arguments: list[str], declared_options: list[str]
) -> tuple[list[CommandParameter], list[CommandParameter]]:
    """Return the arguments and options declared, asked, or the demonstration pair.

    Raises:
        InvalidArgumentError: When a declaration cannot be used.
    """
    if declared_arguments or declared_options:
        return (
            [CommandParameter.parse(typed, option=False) for typed in declared_arguments],
            [CommandParameter.parse(typed, option=True) for typed in declared_options],
        )
    if not io.interactive:
        return [_DEMO[0]], [_DEMO[1]]
    asked: list[CommandParameter] = []
    # A list argument takes every value left, so no argument is asked after one.
    while not (asked and asked[-1].is_list):
        found = _ask_parameter(io, asked, option=False)
        if found is None:
            break
        asked.append(found)
    arguments = list(asked)
    while (found := _ask_parameter(io, asked, option=True)) is not None:
        asked.append(found)
    return arguments, asked[len(arguments) :]


def _ask_parameter(
    io: ConsoleStyle, asked: list[CommandParameter], *, option: bool
) -> CommandParameter | None:
    """Ask for one more argument or option; ``None`` once the name is left empty.

    An argument is asked whether it is required only while every argument
    before it is: an optional one may not be followed by a required one.

    Raises:
        InvalidArgumentError: When no answer names an enum class, after the
            last attempt.
    """
    kind = "option" if option else "argument"
    while True:
        typed = io.ask(f"A new {kind}'s name (press <return> to stop)").strip()
        if not typed:
            return None
        try:
            name = CommandParameter.check_name(typed, option=option)
        except InvalidArgumentError as error:
            io.error(escape(str(error)))
            continue
        if any(found.name == name for found in asked):
            io.error(f"There is already a parameter named {name!r}.")
            continue
        break
    choices = _OPTION_TYPES if option else _ARGUMENT_TYPES
    value_type = _value_type(io, io.ask("Its type", choices[0], choices=choices))
    description = io.ask("Its help text", CommandParameter.default_description(name)).strip()
    required = not option and all(found.required for found in asked)
    if required:
        required = io.confirm("Is it required?", default=True)
    return CommandParameter(
        name,
        value_type,
        option=option,
        required=required,
        description=description or CommandParameter.default_description(name),
    )


def _value_type(io: ConsoleStyle, picked: str) -> str:
    """Return the type ``picked``, asking for the class when it is an enum.

    Raises:
        InvalidArgumentError: When no answer names an enum class, after the
            last attempt.
    """
    if picked == "list":
        return LIST_TYPE
    if picked != "enum":
        return picked
    question = "The enum class, as module.Class"
    for _ in range(_ATTEMPTS - 1):
        try:
            return CommandParameter.check_type(io.ask(question))
        except InvalidArgumentError as error:
            io.error(escape(str(error)))
    return CommandParameter.check_type(io.ask(question))
