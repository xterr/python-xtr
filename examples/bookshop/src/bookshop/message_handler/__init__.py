"""Handlers, as functions and as classes, with every way of receiving what they need.

- The **message** is the first parameter; a second one annotated ``Envelope`` receives the
  envelope. Both are passed by the bus, by position.
- A **function handler** takes everything else from the container through a marker:
  ``Injected[T]``, ``Annotated[T, Target("q")]`` for a qualified service, or
  ``Annotated[T, Autowire(param=... | env=...)]``. A bare ``T`` is not injected.
- A **class handler** is a singleton the container builds: its constructor is injected
  like any service, and ``__call__`` takes what one message needs, with the same markers.

Every handler of a message runs, in declaration order — the scan imports modules sorted by
name — each leaving a ``HandledStamp``. The messenger bundle binds them all at boot, so one
asking for something the container cannot provide fails the boot, not the first message.

Every message is a unit of work: its handlers share one database session — through the
scoped repositories they ask for — and ``orm_transaction``, listed in
``config/packages/messenger.py``, commits what they wrote once they all succeeded, or rolls it
back. No handler commits.
"""

from __future__ import annotations

__all__: list[str] = []
