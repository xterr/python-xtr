"""``make:listener``: a class reacting to one event, as a listener or as a subscriber."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import Injected, as_service
from xtr_event_dispatcher import (  # noqa: TC002 — the container reads annotations at runtime.
    ListenerIntrospectionInterface,
)

from xtr_maker.class_name import ClassName
from xtr_maker.event import EventRegistry, KnownEvent
from xtr_maker.exception import InvalidArgumentError, InvalidClassNameError, TargetExistsError
from xtr_maker.file_manager import (  # noqa: TC001 — the container reads annotations at runtime.
    FileManager,
)
from xtr_maker.generator import Generator  # noqa: TC001 — the console reads annotations at runtime.
from xtr_maker.import_collector import ImportCollector
from xtr_maker.name_converter import NameConverter

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MakeListenerCommand"]


@dataclass(frozen=True, slots=True)
class _Kind:
    """One of the two shapes of class the maker writes, and where it goes."""

    choice: str
    folder: str
    suffix: str
    template: str


_LISTENER: Final = _Kind(
    "listener", "event_listener", "Listener", "listener/event_listener.py.jinja"
)
_SUBSCRIBER: Final = _Kind(
    "subscriber", "event_subscriber", "Subscriber", "listener/event_subscriber.py.jinja"
)

_ATTEMPTS: Final = 3
"""How many times a question is asked: an input that has ended answers empty every time."""

_LINE_LENGTH: Final = 88
"""The formatter's default line length: a longer line is written the way it splits it."""

_INDENT: Final = "    "

_EVENT_NAME: Final = re.compile(r"[A-Za-z0-9_.:-]+")
"""What an event known by name only may be spelled with, to be written as a string."""


@final
@as_command(
    "make:listener",
    description="Write a class reacting to an event: a listener, or a subscriber.",
)
class MakeListenerCommand:
    """Writes ``event_listener/<name>_listener.py`` or ``event_subscriber/<name>_subscriber.py``.

    A listener is a class whose ``on_<event>`` method carries
    ``@as_event_listener``; a subscriber derives from
    ``EventSubscriberInterface`` and maps the event to that method in
    ``get_subscribed_events``. A name ending in ``Listener`` or ``Subscriber``
    picks which; otherwise it is asked, a listener by default.

    The event is a class — typed by its name, ``module:Class`` or a dotted
    path — or a name it is dispatched under. The events of the installed
    packages, of the application's ``event`` package and of the dispatcher are
    listed when it is asked; a name close to some of them is answered with
    what it may have meant. Without a terminal (``-n``) the name and the event
    must be given.
    """

    __slots__ = ("_event_registry", "_file_manager")

    def __init__(self, file_manager: FileManager, event_registry: EventRegistry) -> None:
        """Write into the package ``file_manager`` holds, offering ``event_registry``'s events.

        Args:
            file_manager: The application package the class is written into.
            event_registry: The events a class can be written for.
        """
        self._file_manager = file_manager
        self._event_registry = event_registry

    async def __call__(
        self,
        io: ConsoleStyle,
        generator: Injected[Generator],
        name: str | None = None,
        event: str | None = None,
    ) -> int:
        """Write a listener or a subscriber of one event.

        Args:
            io: Where the command writes, and asks.
            generator: What writes the file.
            name: The class's name, such as ``SendReceiptListener`` or
                ``"sales tally subscriber"``; ``ordering.SendReceipt`` writes it
                under ``ordering/``.
            event: The event: its class's name, ``module:Class``, a dotted
                path, or a name it is dispatched under.
        """
        try:
            typed = self._class_name(io, name)
            kind = _kind(io, typed)
            listened = self._event(io, event)
            target = ClassName(
                root_package=typed.root_package,
                package=(kind.folder, *typed.package[1:]),
                short_name=_with_suffix(typed.short_name, kind.suffix),
                suffix=kind.suffix,
            )
        except (InvalidArgumentError, InvalidClassNameError) as error:
            io.error(escape(str(error)))
            return ExitCode.INVALID
        method = f"on_{NameConverter.as_snake_case(listened.name)}"
        context = _context(target, listened, method, generator, subscriber=kind is _SUBSCRIBER)
        try:
            path = generator.generate_class(target, kind.template, context)
        except TargetExistsError as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        generator.write_changes(io)
        io.success(f"Wrote {target.short_name}, reacting to {escape(listened.reference)}.")
        io.text("Next:")
        io.text(
            f"  - Open {escape(self._file_manager.relative(path))} and write what {method} does."
        )
        return ExitCode.SUCCESS

    def _class_name(self, io: ConsoleStyle, typed: str | None) -> ClassName:
        """Return the class ``typed`` names, asking for it when it was left out.

        Raises:
            InvalidArgumentError: When no name was given and nothing may be asked.
            InvalidClassNameError: When the name given cannot name a class, or
                no answer could after the last attempt.
        """
        if typed is not None:
            return self._typed_class(typed)
        if not io.interactive:
            raise InvalidArgumentError(
                "Name the class to write: make:listener <name> <event>,"
                " such as make:listener SendReceiptListener OrderPlaced."
            )
        question = (
            "The class name (such as [cyan]SendReceiptListener[/];"
            " ending in [cyan]Subscriber[/] writes a subscriber)"
        )
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._typed_class(io.ask(question))
            except InvalidClassNameError as error:
                io.error(escape(str(error)))
        return self._typed_class(io.ask(question))

    def _typed_class(self, typed: str) -> ClassName:
        return ClassName.create(
            typed, root_package=self._file_manager.root_package, kind=_LISTENER.folder
        )

    def _event(self, io: ConsoleStyle, typed: str | None) -> KnownEvent:
        """Return the event ``typed`` names, asking for it when it was left out or not found.

        Raises:
            InvalidArgumentError: When no event was given and nothing may be
                asked, when the one given names no event without a terminal,
                or when no answer did after the last attempt.
        """
        if typed is not None:
            try:
                return self._resolve(io, typed)
            except InvalidArgumentError as error:
                if not io.interactive:
                    raise
                io.error(escape(str(error)))
        elif not io.interactive:
            raise InvalidArgumentError(
                "Name the event to listen to: make:listener <name> <event>,"
                " such as make:listener SendReceiptListener OrderPlaced."
            )
        labels = self._event_registry.labels()
        if labels:
            io.text("The events found:")
            io.listing(escape(label) for label in labels)
        question = "The event to listen to (its class, [cyan]module:Class[/], or a dotted path)"
        for _ in range(_ATTEMPTS - 1):
            try:
                return self._resolve(io, io.ask(question))
            except InvalidArgumentError as error:
                io.error(escape(str(error)))
        return self._resolve(io, io.ask(question))

    def _resolve(self, io: ConsoleStyle, typed: str) -> KnownEvent:
        """Return the event ``typed`` names, or the one it was close to and confirmed.

        Raises:
            InvalidArgumentError: When ``typed`` names no event, or an event
                name that cannot be written.
        """
        text = typed.strip()
        if not text:
            raise InvalidArgumentError("Name the event to listen to.")
        found = self._event_registry.find(text)
        if found is not None:
            return _writable(found)
        suggestions = self._event_registry.suggestions(text)
        if suggestions:
            if io.interactive and len(suggestions) == 1:
                if io.confirm(f"Did you mean {escape(suggestions[0].label)}?", default=True):
                    return _writable(suggestions[0])
                raise InvalidArgumentError(f"There is no event {text!r}.")
            raise InvalidArgumentError(
                f"There is no event {text!r}; did you mean {_one_of(suggestions)}?"
            )
        if io.interactive and io.confirm(
            f"No event class is named {escape(repr(text))}."
            f" Listen to {escape(repr(text))} as the name an event is dispatched under?"
        ):
            return _writable(KnownEvent(text))
        raise InvalidArgumentError(
            f"There is no event {text!r}: give an event class's name, module:Class,"
            " or a dotted path to it."
        )


@as_service
def _event_registry(
    file_manager: FileManager, listener_introspection: ListenerIntrospectionInterface
) -> EventRegistry:
    """List the events of the installed xtr packages, the application and the dispatcher."""
    return EventRegistry(
        listener_introspection, file_manager.root_package, EventRegistry.installed_packages()
    )


def _kind(io: ConsoleStyle, typed: ClassName) -> _Kind:
    """Return the shape the name's ending picks, else the one asked for, a listener by default."""
    for kind in (_LISTENER, _SUBSCRIBER):
        if typed.short_name.endswith(kind.suffix):
            return kind
    answer = io.ask(
        "Write a listener or a subscriber",
        _LISTENER.choice,
        choices=(_LISTENER.choice, _SUBSCRIBER.choice),
    )
    return _SUBSCRIBER if answer == _SUBSCRIBER.choice else _LISTENER


def _with_suffix(short_name: str, suffix: str) -> str:
    return short_name if short_name.endswith(suffix) else f"{short_name}{suffix}"


def _writable(event: KnownEvent) -> KnownEvent:
    """Return ``event``, refusing an event name the generated code cannot spell.

    Raises:
        InvalidArgumentError: When an event known by name only holds a
            character a string in the code would need escaped, or no word to
            name its method after.
    """
    if event.module is None and (
        _EVENT_NAME.fullmatch(event.name) is None or not NameConverter.as_snake_case(event.name)
    ):
        raise InvalidArgumentError(
            f"The event name {event.name!r} cannot be written: use letters, digits,"
            " and '.', '_', ':' or '-' between them."
        )
    return event


def _one_of(events: Sequence[KnownEvent]) -> str:
    references = ", ".join(event.reference for event in events)
    return references if len(events) == 1 else f"one of {references}"


def _context(
    target: ClassName,
    event: KnownEvent,
    method: str,
    generator: Generator,
    *,
    subscriber: bool,
) -> dict[str, object]:
    """Return what the listener or subscriber template reads.

    The event class is imported at runtime: the listener names it in its
    decorator, the subscriber in the map ``get_subscribed_events`` returns.
    """
    imports = ImportCollector(target.root_package)
    if generator.final_classes:
        _ = imports.add("typing", "final")
    if event.module is None:
        key = _literal(event.name)
        event_type = imports.add("xtr_event_dispatcher", "Event", type_checking=True)
        described = event.name
    else:
        key = event_type = described = imports.add(event.module, event.name)
    context: dict[str, object] = {
        "event": described,
        "signature": _signature(method, event_type),
    }
    if subscriber:
        context["mapping"] = imports.add("collections.abc", "Mapping", type_checking=True)
        context["override"] = imports.add("typing_extensions", "override")
        context["interface"] = imports.add("xtr_event_dispatcher", "EventSubscriberInterface")
        context["subscribed_events"] = imports.add(
            "xtr_event_dispatcher", "SubscribedEvents", type_checking=True
        )
        context["subscribed"] = _subscribed(key, method)
    else:
        decorator = imports.add("xtr_event_dispatcher", "as_event_listener")
        context["as_event_listener"] = _decorator(decorator, key)
    context["imports"] = imports.render()
    return context


def _literal(value: str) -> str:
    """Return ``value`` as a double-quoted string literal, the quotes the formatter writes."""
    return json.dumps(value, ensure_ascii=False)


def _decorator(decorator: str, argument: str) -> str:
    """Return ``@decorator(argument)`` for a method, split the way the formatter splits it."""
    line = f"@{decorator}({argument})"
    if len(_INDENT + line) <= _LINE_LENGTH:
        return line
    return f"@{decorator}(\n{_INDENT * 2}{argument}\n{_INDENT})"


def _signature(method: str, event_type: str) -> str:
    """Return the method's ``async def`` line, split the way the formatter splits it."""
    line = f"async def {method}(self, event: {event_type}) -> None:"
    if len(_INDENT + line) <= _LINE_LENGTH:
        return line
    parameters = f"{_INDENT * 2}self, event: {event_type}"
    if len(parameters) <= _LINE_LENGTH:
        return f"async def {method}(\n{parameters}\n{_INDENT}) -> None:"
    return (
        f"async def {method}(\n{_INDENT * 2}self,\n{_INDENT * 2}event: {event_type},\n"
        f"{_INDENT}) -> None:"
    )


def _subscribed(key: str, method: str) -> str:
    """Return the ``return`` of ``get_subscribed_events``, split the way the formatter splits it."""
    entry = f"{key}: {_literal(method)}"
    line = f"return {{{entry}}}"
    if len(_INDENT * 2 + line) <= _LINE_LENGTH:
        return line
    return f"return {{\n{_INDENT * 3}{entry}\n{_INDENT * 2}}}"
