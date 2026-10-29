"""The events ``make:listener`` can write a listener for.

Imported only by that maker, which is offered only when the event dispatcher
bundle is active: this package needs the event dispatcher installed.

* :class:`~xtr_maker.event.event_registry.EventRegistry` — every event found
  in the installed packages, the application and the dispatcher.
* :class:`~xtr_maker.event.known_event.KnownEvent` — one of them, as the
  generated code imports it.
"""

from __future__ import annotations

from .event_registry import EventRegistry
from .known_event import KnownEvent

__all__ = ["EventRegistry", "KnownEvent"]
