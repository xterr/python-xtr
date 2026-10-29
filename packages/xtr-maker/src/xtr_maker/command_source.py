"""CommandSource: the parts of a console command's module its template cannot spell itself."""

from __future__ import annotations

import json
import textwrap
from typing import TYPE_CHECKING, Final, final

from .exception import InvalidArgumentError
from .import_collector import ImportCollector

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .command_parameter import CommandParameter

__all__ = ["CommandSource"]

_LINE_LENGTH: Final = 88
"""The formatter's default line length: a longer line is split the way it splits it."""

_MAX_ARGUMENTS: Final = 5
"""The most parameters the linter lets a function take before it asks for a reason."""

_INDENT: Final = "    "


@final
class CommandSource:
    """A console command's name, description and parameters, as the lines its module holds.

    The parameters are checked together here — each one checked itself on its
    own — so the signature they make is one the console accepts: names are
    unique, an optional argument is never followed by a required one, and a
    list argument, which takes every value left, comes last.

    :meth:`context` returns what the ``command/command.py.jinja`` template
    reads: the imports, the ``@as_command`` line, the ``__call__`` signature,
    its docstring's ``Args:`` lines and a body echoing every parameter, each
    written the way the formatter and the linter want it.

    An enum class is imported at runtime, with the other imports: the console
    evaluates a command's annotations to read its command line, so it cannot
    sit under ``if TYPE_CHECKING:`` — which is why an application declaring
    commands turns the linter's rules moving it there off.
    """

    __slots__ = ("_arguments", "_description", "_name", "_options")

    def __init__(
        self,
        name: str,
        description: str,
        arguments: Sequence[CommandParameter],
        options: Sequence[CommandParameter],
    ) -> None:
        """Hold the command ``name`` and what its ``--help`` shows.

        Args:
            name: The console name, such as ``app:send-report``.
            description: The summary ``--help`` and ``list`` show.
            arguments: Its arguments, in the order they are typed.
            options: Its options.

        Raises:
            InvalidArgumentError: When two parameters share a name, a list
                argument is not the last argument, or a required argument
                follows an optional one.
        """
        self._name = name
        self._description = description
        self._arguments = tuple(arguments)
        self._options = tuple(options)
        _check_together(self._arguments, self._options)

    def context(self, root_package: str, *, final_classes: bool) -> dict[str, object]:
        """Return what the command template reads, for a module of ``root_package``."""
        imports = ImportCollector(root_package)
        if final_classes:
            _ = imports.add("typing", "final")
        decorator = imports.add("xtr_console", "as_command")
        style = imports.add("xtr_console", "ConsoleStyle")
        exit_code = imports.add("xtr_console", "ExitCode")
        escape = imports.add("xtr_console", "escape") if self._parameters else ""
        type_names: dict[str, str] = {}
        for parameter in self._parameters:
            found = parameter.enum_class
            if found is not None:
                type_names[parameter.value_type] = imports.add(*found)
        arguments = [f"description={_literal(self._description)}"]
        return {
            "command_name": self._name,
            "imports": imports.render(),
            "as_command": _call(decorator, [_literal(self._name), *arguments]),
            "signature": self._signature(style, type_names),
            "arguments": self._docstring_arguments(),
            "body": [f"io.text({escape}(f{_literal(f'{{{p.name}=}}')}))" for p in self._parameters],
            "success": f"io.success({_literal(f'{self._name} ran.')})",
            "exit_code": exit_code,
        }

    @property
    def _parameters(self) -> tuple[CommandParameter, ...]:
        return (*self._arguments, *self._options)

    def _signature(self, style: str, type_names: dict[str, str]) -> str:
        """Return ``async def __call__(...) -> int:``, split one parameter per line when long.

        ``type_names`` holds the name each enum class is imported under, by its path.
        """
        declared = [
            parameter.declaration(type_names.get(parameter.value_type, parameter.value_type))
            for parameter in self._parameters
        ]
        if self._options:
            declared.insert(len(self._arguments), "*")
        parameters = ["self", f"io: {style}", *declared]
        line = f"{_INDENT}async def __call__({', '.join(parameters)}) -> int:"
        many = len(self._parameters) + 1 > _MAX_ARGUMENTS
        if len(line) <= _LINE_LENGTH and not many:
            return line
        comment = "  # noqa: PLR0913 — one parameter per argument and option." if many else ""
        lines = "".join(f"{_INDENT * 2}{parameter},\n" for parameter in parameters)
        return f"{_INDENT}async def __call__({comment}\n{lines}{_INDENT}) -> int:"

    def _docstring_arguments(self) -> list[str]:
        """Return the ``Args:`` lines, each wrapped to the line length under its indent."""
        described = [("io", "Where the command writes."), *self._described()]
        lines: list[str] = []
        for name, description in described:
            lines.extend(
                textwrap.wrap(
                    f"{name}: {description}",
                    width=_LINE_LENGTH,
                    initial_indent=_INDENT * 3,
                    subsequent_indent=_INDENT * 4,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        return lines

    def _described(self) -> list[tuple[str, str]]:
        return [(parameter.name, parameter.description) for parameter in self._parameters]


def _check_together(
    arguments: tuple[CommandParameter, ...], options: tuple[CommandParameter, ...]
) -> None:
    """Refuse parameters that are each valid but cannot share one signature.

    Raises:
        InvalidArgumentError: When the parameters cannot share one signature.
    """
    seen: set[str] = set()
    for parameter in (*arguments, *options):
        if parameter.name in seen:
            raise InvalidArgumentError(f"Two parameters are named {parameter.name!r}.")
        seen.add(parameter.name)
    for argument in arguments[:-1]:
        if argument.is_list:
            raise InvalidArgumentError(
                f"List argument {argument.name!r} takes every value left, so it must come last."
            )
    optional = next((argument for argument in arguments if not argument.required), None)
    if optional is None:
        return
    for argument in arguments[arguments.index(optional) + 1 :]:
        if argument.required:
            raise InvalidArgumentError(
                f"Required argument {argument.name!r} cannot follow optional"
                f" argument {optional.name!r}."
            )


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)


def _call(decorator: str, arguments: list[str]) -> str:
    """Return ``@decorator(...)`` on one line, or one argument per line when that is too long."""
    line = f"@{decorator}({', '.join(arguments)})"
    if len(line) <= _LINE_LENGTH:
        return line
    lines = "".join(f"{_INDENT}{argument},\n" for argument in arguments)
    return f"@{decorator}(\n{lines})"
