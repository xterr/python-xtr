"""``make:message``: a message class, and the handler that handles it."""

from __future__ import annotations

import json
from typing import Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import (  # noqa: TC002 — the console reads annotations at runtime.
    Injected,
)
from xtr_messenger import (  # noqa: TC002 — the container reads annotations at runtime.
    MessageBusConfig,
)

from xtr_maker.class_name import ClassName
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.
from xtr_maker.import_collector import ImportCollector

__all__ = ["MakeMessageCommand"]

_NO_TRANSPORT: Final = "[no transport]"
"""The transport choice that leaves the message to the routing table."""

_ATTEMPTS: Final = 3
"""How many times the name is asked: an input that has ended answers empty every time."""

_LINE_LENGTH: Final = 88
"""The formatter's default line length: a longer decorator is written one argument per line."""

_MESSAGE_TEMPLATE: Final = "message/message.py.jinja"
_HANDLER_TEMPLATE: Final = "message/message_handler.py.jinja"


@final
@as_command("make:message", description="Write a message class and the handler that handles it.")
class MakeMessageCommand:
    """Writes ``message/<name>.py`` and ``message_handler/<name>_handler.py``.

    The message is a frozen dataclass declared with ``@as_message``: it travels
    under a pinned, versioned wire name, so moving the class later changes
    nothing on the wire, and names the transport it goes to by default when
    one is picked. The handler is a class whose ``__call__`` takes it.

    Whatever is not on the command line is asked: the name, the transport
    (only when transports are configured) and the wire name. Without a
    terminal (``-n``) the transport is none and the wire name its default,
    but the name must be given.
    """

    __slots__ = ("_file_manager", "_transports")

    def __init__(self, file_manager: FileManager, config: MessageBusConfig) -> None:
        """Write into the package ``file_manager`` holds, offering ``config``'s transports.

        Args:
            file_manager: The application package the classes are written into.
            config: The bus configuration; its transports are the ones offered.
        """
        self._file_manager = file_manager
        self._transports = tuple(config.transports)

    async def __call__(
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        *,
        transport: str | None = None,
        wire_name: str | None = None,
    ) -> int:
        """Write a message class and its handler.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the files, all or none.
            name: The message's class name, such as ``PlaceOrder`` or
                ``"place order"``; ``ordering.PlaceOrder`` writes it under
                ``message/ordering/``.
            transport: The configured transport the message goes to when the
                routing table names none.
            wire_name: The name the message travels under; defaults to
                ``<package>.<name>.v1``.
        """
        try:
            message = self._message_name(io, name)
            picked = self._transport(io, transport)
            wire = self._wire_name(io, wire_name, message)
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        handler = ClassName.create(
            ".".join((*message.package[1:], message.short_name)),
            root_package=message.root_package,
            kind="message_handler",
            suffix="Handler",
        )
        try:
            message_path = generator.generate_class(
                message, _MESSAGE_TEMPLATE, _message_context(message, wire, picked, generator)
            )
            handler_path = generator.generate_class(
                handler, _HANDLER_TEMPLATE, _handler_context(message, generator)
            )
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(f"Wrote {message.short_name} and {handler.short_name}.")
        io.text("Next:")
        io.text(f"  - Open {escape(self._file_manager.relative(message_path))} and add its fields.")
        io.text(
            f"  - Open {escape(self._file_manager.relative(handler_path))}"
            " and write what handling it does."
        )
        return ExitCode.SUCCESS

    def _message_name(self, io: ConsoleStyle, typed: str | None) -> ClassName:
        """Return the message class ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be asked.
            InvalidClassNameError: When the name given cannot name a class, or
                no answer could after the last attempt.
        """
        if typed is not None:
            return self._message_class(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the message to write: make:message <name>, such as make:message PlaceOrder."
            )
        question = "The message's class name (such as [cyan]PlaceOrder[/])"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._message_class(io.ask(question))
            except InvalidClassNameError as error:
                io.error(escape(str(error)))
        return self._message_class(io.ask(question))

    def _message_class(self, typed: str) -> ClassName:
        return ClassName.create(typed, root_package=self._file_manager.root_package, kind="message")

    def _transport(self, io: ConsoleStyle, typed: str | None) -> str | None:
        """Return the transport ``typed`` names, asking when transports exist; ``None`` for none.

        Raises:
            InvalidArgumentError: When ``typed`` is not a configured transport.
        """
        if typed is not None:
            if not self._transports:
                raise InvalidArgumentError(
                    f"No transports are configured, so the message cannot name {typed!r};"
                    " leave --transport out."
                )
            if typed not in self._transports:
                raise InvalidArgumentError(
                    f"There is no transport {typed!r}; the configured ones are"
                    f" {', '.join(self._transports)}."
                )
            return typed
        if not self._transports:
            return None
        answer = io.ask(
            "The transport it goes to when no route names one",
            _NO_TRANSPORT,
            choices=(_NO_TRANSPORT, *self._transports),
        )
        return None if answer == _NO_TRANSPORT else answer

    @staticmethod
    def _wire_name(io: ConsoleStyle, typed: str | None, message: ClassName) -> str:
        """Return the wire name ``typed``, or the one asked for, defaulting to a versioned one.

        Raises:
            InvalidArgumentError: When the wire name is empty.
        """
        dotted = ".".join((message.root_package, *message.package[1:], message.snake_name))
        default = f"{dotted}.v1"
        answer = typed if typed is not None else io.ask("The name it travels under", default)
        wire = answer.strip()
        if not wire:
            raise InvalidArgumentError("The wire name cannot be empty.")
        return wire


def _message_context(
    message: ClassName, wire: str, transport: str | None, generator: Generator
) -> dict[str, object]:
    """Return what the message template reads: its imports and its ``@as_message`` line."""
    imports = ImportCollector(message.root_package)
    _ = imports.add("dataclasses", "dataclass")
    if generator.final_classes:
        _ = imports.add("typing", "final")
    decorator = imports.add("xtr_messenger", "as_message")
    arguments = [f"name={_literal(wire)}"]
    if transport is not None:
        arguments.append(f"transport={_literal(transport)}")
    return {"imports": imports.render(), "as_message": _call(decorator, arguments)}


def _handler_context(message: ClassName, generator: Generator) -> dict[str, object]:
    """Return what the handler template reads: its imports and the message's name there."""
    imports = ImportCollector(message.root_package)
    if generator.final_classes:
        _ = imports.add("typing", "final")
    _ = imports.add("xtr_messenger", "as_message_handler")
    message_class = imports.add(message.module, message.short_name)
    return {"imports": imports.render(), "message_class": message_class}


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)


def _call(decorator: str, arguments: list[str]) -> str:
    """Return ``@decorator(...)`` on one line, or one argument per line when that is too long."""
    line = f"@{decorator}({', '.join(arguments)})"
    if len(line) <= _LINE_LENGTH:
        return line
    lines = "".join(f"    {argument},\n" for argument in arguments)
    return f"@{decorator}(\n{lines})"
