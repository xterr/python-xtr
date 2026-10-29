"""KnownEvent: an event a listener can be written for, as the generated code names it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["KnownEvent"]


@final
@dataclass(frozen=True, slots=True)
class KnownEvent:
    """An event class, and the module it is imported from — or an event known by name only.

    A listener listens to an event class or to a plain name the event is
    dispatched under. A class is named the way an import names it: its own
    name and a module exporting it, which may be a package re-exporting it
    rather than the module defining it. A named event has no module.

    Attributes:
        name: The class's name, or the event's name.
        module: The dotted module the class is imported from; ``None`` for an
            event known by name only.
    """

    name: str
    module: str | None = None

    @property
    def reference(self) -> str:
        """The class as ``module:Class``, or the event's name."""
        return self.name if self.module is None else f"{self.module}:{self.name}"

    @property
    def label(self) -> str:
        """How the event is listed: ``Class (module)``, or the name in quotes."""
        return f'"{self.name}"' if self.module is None else f"{self.name} ({self.module})"
