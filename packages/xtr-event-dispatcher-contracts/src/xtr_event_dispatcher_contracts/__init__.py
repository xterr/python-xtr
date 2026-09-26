"""The event dispatching contract: what code that emits events depends on, and nothing more.

Code that announces something happened — an order placed, a message
consumed — should not decide who hears it. It takes an
:class:`EventDispatcherInterface` and hands it an event object; the
application decides which listeners run, in which order, and whether any of
them stops the rest. Depending on this package costs a library nothing but
the contract.

```python
@dataclass(frozen=True)
class OrderPlaced(Event):
    order_id: int


await dispatcher.dispatch(OrderPlaced(42))
```

- :class:`EventDispatcherInterface` — dispatch an event.
- :class:`Event` / :class:`StoppableEventInterface` — an event a listener can
  stop.
- :class:`ListenerIntrospectionInterface` — which listeners an event has.
- :data:`Listener` and :func:`event_name_of` — what a listener is called
  with, and the name an event is known by.

``xtr-event-dispatcher`` implements it, and re-exports every symbol here so
the two are never two different objects.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .event import Event
from .event_dispatcher_interface import EventDispatcherInterface
from .event_name_of import event_name_of
from .listener import Listener
from .listener_introspection_interface import ListenerIntrospectionInterface
from .stoppable_event_interface import StoppableEventInterface

try:
    __version__ = version("xtr-event-dispatcher-contracts")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree or a vendored copy, with no installed
    # metadata to read. Having no version is better than refusing to import.
    __version__ = "0+unknown"

__all__ = [
    "Event",
    "EventDispatcherInterface",
    "Listener",
    "ListenerIntrospectionInterface",
    "StoppableEventInterface",
    "__version__",
    "event_name_of",
]
