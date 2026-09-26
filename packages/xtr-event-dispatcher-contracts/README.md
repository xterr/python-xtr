<div align="center">

# xtr-event-dispatcher-contracts

**The event dispatching contract, and nothing else — so a library that emits events installs nothing else.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="core dependencies: 0" src="https://img.shields.io/badge/core%20deps-0-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that announces what happened — an order placed, a message consumed — should not
decide who hears it. It takes an event dispatcher, hands it an event object, and leaves the
listeners to the application that wires it. That needs the *contract*, not a dispatcher:

- 📣 **`EventDispatcherInterface`** — `await dispatcher.dispatch(event)`, and the event comes back.
- 🛑 **`Event`** / **`StoppableEventInterface`** — an event any listener can stop.
- 🔎 **`ListenerIntrospectionInterface`** — which listeners an event has, and in which order.
- 🧷 **`Listener`** and **`event_name_of()`** — what a listener is called with, and the name an
  event is known by.
- 🪶 **No dependencies.**

```python
from dataclasses import dataclass

from xtr_event_dispatcher_contracts import Event, EventDispatcherInterface


@dataclass(frozen=True)
class MessageConsumed(Event):
    message_id: str


class Worker:
    def __init__(self, events: EventDispatcherInterface) -> None:
        self._events = events

    async def handled(self, message_id: str) -> None:
        await self._events.dispatch(MessageConsumed(message_id))
```

## Install

```sh
uv add xtr-event-dispatcher-contracts
```

Requires Python 3.11+.

## Who installs what

|  | Depends on |
| --- | --- |
| **A library that emits events** | `xtr-event-dispatcher-contracts` at runtime. |
| **An application** | [xtr-event-dispatcher](../xtr-event-dispatcher), which implements this contract and wires listeners from a container. |

`xtr-event-dispatcher` **re-exports** `Event`, `StoppableEventInterface`,
`ListenerIntrospectionInterface`, `Listener` and `event_name_of` rather than redefining them, so a
library written against this package and an application using that one share the same objects.
Its own `EventDispatcherInterface` extends the one here with registering listeners.

## The contract

```python
class EventDispatcherInterface(Protocol):
    async def dispatch(self, event: T, event_name: str | type | None = None) -> T: ...
```

- **Names.** Events are keyed by name: a string, or a class standing for
  `"<module>.<qualname>"` (`event_name_of`). Without a name, an event is dispatched under its
  class's.
- **Order.** Listeners run highest priority first, one after the other, each awaited before the
  next. An exception a listener raises reaches the caller unchanged.
- **Stopping.** An event that is a `StoppableEventInterface` stops reaching listeners once one
  stops it. `Event` is the base class that does this, frozen dataclasses included:
  `event.stop_propagation()`.
- **Listeners** (`Listener`) are called with the event, its name and the dispatcher — as many
  of the three as they take, by position; an awaitable result is awaited.

`ListenerIntrospectionInterface` reads listeners without registering any: `get_listeners(name)`
in running order (or every event's, given no name), `get_listener_priority(name, listener)`,
`has_listeners(name=None)`.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-event-dispatcher-contracts`; run the commands below from there. The
`python-xtr-event-dispatcher-contracts` repository is a read-only copy, so send issues and pull
requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
