"""Declare the sources a consumer answers for, and read back what was declared."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, cast

from xtr_remote_event.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "CONSUMERS_ATTRIBUTE",
    "as_remote_event_consumer",
    "remote_event_consumers_declared_on",
]

CONSUMERS_ATTRIBUTE: Final = "__xtr_remote_event_consumers__"

ConsumerT = TypeVar("ConsumerT", bound=type[object])


def as_remote_event_consumer(name: str) -> Callable[[ConsumerT], ConsumerT]:
    """Declare the decorated class the consumer of the events named ``name``.

    For example::

        @as_remote_event_consumer("stripe")
        class PaymentConsumer:
            async def consume(self, event: RemoteEvent) -> None: ...

    Stack the decorator for a consumer answering for several sources. The
    names are recorded in the order the decorators run — from the one nearest
    the class outwards — so what is read back reads as it was written.

    The declaration is written on the class itself rather than into a registry
    of this module's own, so whatever gathers consumers finds it where it finds
    the class: a container's scan sees it, and a test that declares one leaves
    nothing behind for the next. Read it back with
    :func:`remote_event_consumers_declared_on`.

    Raises:
        InvalidArgumentError: If ``name`` is empty, or the class has no
            ``consume()`` to hand an event to. Both are mistakes in the
            declaration, so they are refused where it is written instead of
            when the first event arrives for it.
    """
    if not name:
        raise InvalidArgumentError("A remote event consumer needs a non-empty name.")

    def declare(consumer: ConsumerT) -> ConsumerT:
        if not callable(getattr(consumer, "consume", None)):
            raise InvalidArgumentError(
                f"{consumer.__qualname__} must define consume() to be a remote event consumer."
            )
        declared = remote_event_consumers_declared_on(consumer)
        setattr(consumer, CONSUMERS_ATTRIBUTE, (*declared, name))
        return consumer

    return declare


def remote_event_consumers_declared_on(obj: object) -> tuple[str, ...]:
    """Return the names ``obj`` itself was declared the consumer of.

    Only what was written on ``obj``, never what a base class carries: a
    subclass of a consumer declares nothing until it is decorated too.
    Inheriting would have every derived class quietly answering for its
    parent's sources, and whoever gathers consumers finding two for one name.
    """
    recorded: object = vars(obj).get(CONSUMERS_ATTRIBUTE, ()) if hasattr(obj, "__dict__") else ()
    declared = cast("tuple[object, ...]", recorded) if isinstance(recorded, tuple) else ()
    return tuple(name for name in declared if isinstance(name, str))
