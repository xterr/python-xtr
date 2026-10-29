"""EventRegistry: every event an application can write a listener for, found where it lives."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
import re
import sys
from importlib.metadata import distributions
from typing import TYPE_CHECKING, Final, cast, final

from xtr_event_dispatcher import Event

from xtr_maker.exception import InvalidArgumentError

from .known_event import KnownEvent

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from types import ModuleType

    from xtr_event_dispatcher import ListenerIntrospectionInterface

__all__ = ["EventRegistry"]

_EVENT_MODULE: Final = "event"
"""The module a package, and the application, keeps its events in."""

_ABSTRACT_PREFIX: Final = "Abstract"
"""What a base class only other events derive from is named with; nothing dispatches it."""

_MAX_DISTANCE: Final = 3
"""A suggestion is less than this many single-character edits away from what was typed."""

_SEPARATORS: Final = re.compile(r"[-_.]+")


@final
class EventRegistry:
    """Finds the events a listener can be written for, and resolves what a person typed to one.

    Events come from three places, read the first time they are needed:

    * every package given — the installed ``xtr-*`` ones, from
      :meth:`installed_packages` — exporting ``Event`` subclasses from its
      ``event`` module or from the package itself;
    * the application's own ``event`` package, every module in it;
    * the dispatcher: every event a listener is registered for already. An
      event class is read from the module already imported; an event name no
      class stands for is listed as a name.

    A class exported from several modules is listed once, under the first
    found: the package's ``event`` module before the package. A package that
    fails to import is skipped — an optional dependency missing, say — so one
    broken package never hides the others' events.
    """

    __slots__ = ("_events", "_listener_introspection", "_packages", "_root_package")

    def __init__(
        self,
        listener_introspection: ListenerIntrospectionInterface,
        root_package: str,
        packages: Sequence[str],
    ) -> None:
        """Read events from ``listener_introspection``, the application, and ``packages``.

        Args:
            listener_introspection: The dispatcher, whose listened-to events are listed.
            root_package: The application package, dotted; its ``event``
                package is scanned.
            packages: The importable packages whose exported events are listed.
        """
        self._listener_introspection = listener_introspection
        self._root_package = root_package
        self._packages = tuple(packages)
        self._events: tuple[KnownEvent, ...] | None = None

    @staticmethod
    def installed_packages() -> tuple[str, ...]:
        """Return the import name of every installed ``xtr-*`` distribution, sorted.

        The import name is the distribution's name, snake-cased: every xtr
        package is laid out that way.
        """
        names = {
            _import_name(cast("str | None", found.metadata["Name"])) for found in distributions()
        }
        return tuple(sorted(name for name in names if name.startswith("xtr_")))

    def events(self) -> tuple[KnownEvent, ...]:
        """Return every event found, ordered by name, then by module."""
        if self._events is None:
            self._events = tuple(
                sorted(self._collect(), key=lambda event: (event.name.lower(), event.module or ""))
            )
        return self._events

    def labels(self) -> tuple[str, ...]:
        """Return how each event of :meth:`events` is listed, in the same order.

        A class sharing its name with another is listed as ``module:Class``,
        the way it must be typed.
        """
        counts: dict[str, int] = {}
        for event in self.events():
            counts[event.name] = counts.get(event.name, 0) + 1
        return tuple(
            event.reference if counts[event.name] > 1 else event.label for event in self.events()
        )

    def find(self, typed: str) -> KnownEvent | None:
        """Return the event ``typed`` names, or ``None`` when it names none.

        Args:
            typed: A class name (``OrderPlaced``), ``module:Class``, a dotted
                path to a class, or the name of an event known by name.

        Raises:
            InvalidArgumentError: When a class name is shared by several events.
        """
        text = typed.strip()
        if ":" in text:
            module, _, name = text.partition(":")
            return self._known(module, name) or _imported(module, name)
        named = [event for event in self.events() if event.name == text]
        if len(named) > 1:
            references = ", ".join(event.reference for event in named)
            raise InvalidArgumentError(
                f"{text!r} names several events: {references}; type the one you mean."
            )
        if named:
            return named[0]
        module, _, name = text.rpartition(".")
        if not module:
            return None
        return self._known(module, name) or _imported(module, name)

    def suggestions(self, typed: str) -> tuple[KnownEvent, ...]:
        """Return the events whose name is close to ``typed``, the closest first.

        Close is fewer than three single-character edits, case left aside; the
        class part of ``module:Class`` or of a dotted path is compared too.
        """
        text = typed.strip().lower()
        candidates = {text, text.rpartition(":")[2], text.rpartition(".")[2]} - {""}
        ranked: list[tuple[int, KnownEvent]] = []
        for event in self.events():
            distance = min(_distance(candidate, event.name.lower()) for candidate in candidates)
            if distance < _MAX_DISTANCE:
                ranked.append((distance, event))
        ranked.sort(key=lambda found: (found[0], found[1].name.lower(), found[1].module or ""))
        return tuple(event for _, event in ranked)

    def _known(self, module: str, name: str) -> KnownEvent | None:
        return next(
            (event for event in self.events() if (event.module, event.name) == (module, name)),
            None,
        )

    def _collect(self) -> list[KnownEvent]:
        """Return every event, a class once under the first module found exporting it."""
        classes: dict[type, KnownEvent] = {}
        for package in self._packages:
            for module_name in (f"{package}.{_EVENT_MODULE}", package):
                module = _module(module_name)
                if module is not None:
                    for found in _exported_events(module):
                        _ = classes.setdefault(found, KnownEvent(found.__name__, module_name))
        for module in self._application_modules():
            for found in _defined_events(module):
                _ = classes.setdefault(found, KnownEvent(found.__name__, module.__name__))
        named: list[KnownEvent] = []
        for event_name in self._listener_introspection.get_listeners():
            found = _class_named(event_name)
            if found is None:
                named.append(KnownEvent(event_name))
            else:
                _ = classes.setdefault(found, KnownEvent(found.__name__, found.__module__))
        return [*classes.values(), *named]

    def _application_modules(self) -> Iterator[ModuleType]:
        """Yield the application's ``event`` package and every module under it."""
        package = _module(f"{self._root_package}.{_EVENT_MODULE}")
        if package is None:
            return
        yield package
        path = cast("Sequence[str]", getattr(package, "__path__", ()))
        for found in pkgutil.walk_packages(path, prefix=f"{package.__name__}."):
            module = _module(found.name)
            if module is not None:
                yield module


def _import_name(distribution: str | None) -> str:
    """Return the import name of the distribution ``distribution``: ``xtr-orm`` → ``xtr_orm``."""
    return _SEPARATORS.sub("_", distribution or "").lower()


def _module(name: str) -> ModuleType | None:
    """Return the module ``name``, imported; ``None`` when there is none or it fails to import."""
    try:
        if importlib.util.find_spec(name) is None:
            return None
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 — a module failing to import, whatever the reason, offers no events.
        return None


def _imported(module: str, name: str) -> KnownEvent | None:
    """Return the class ``name`` of ``module`` as an event; ``None`` when it is no class there."""
    found = _module(module)
    candidate: object = getattr(found, name, None) if found is not None else None
    if not name.isidentifier() or not isinstance(candidate, type):
        return None
    return KnownEvent(name, module)


def _exported_events(module: ModuleType) -> Iterator[type]:
    """Yield the events ``module`` lists in its ``__all__``."""
    exported = cast("Sequence[object]", getattr(module, "__all__", ()))
    for name in exported:
        if isinstance(name, str):
            candidate: object = getattr(module, name, None)
            if _is_event(candidate):
                yield cast("type", candidate)


def _defined_events(module: ModuleType) -> Iterator[type]:
    """Yield the events ``module`` defines itself, not those it imports."""
    for candidate in cast("dict[str, object]", vars(module)).values():
        if _is_event(candidate) and cast("type", candidate).__module__ == module.__name__:
            yield cast("type", candidate)


def _is_event(candidate: object) -> bool:
    """Report whether ``candidate`` is an event class a dispatcher can dispatch."""
    return (
        isinstance(candidate, type)
        and issubclass(candidate, Event)
        and candidate is not Event
        and not candidate.__name__.startswith(_ABSTRACT_PREFIX)
        and not inspect.isabstract(candidate)
    )


def _class_named(event_name: str) -> type | None:
    """Return the class the dispatcher's ``module.Class`` event name stands for, if imported.

    Only modules already imported are read: a listener for the event was
    registered, so the module defining its class was imported with it.
    """
    module_name, _, name = event_name.rpartition(".")
    module = sys.modules.get(module_name)
    candidate: object = getattr(module, name, None) if module is not None else None
    return candidate if isinstance(candidate, type) else None


def _distance(first: str, second: str) -> int:
    """Return how many single-character insertions, deletions or changes turn one into the other."""
    previous = list(range(len(second) + 1))
    for row, left in enumerate(first, start=1):
        current = [row]
        for column, right in enumerate(second, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]
