"""Assertions over the notifications an application sent or queued."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_notifier.event import MessageEvent, NotificationEvents
    from xtr_notifier.message import MessageInterface

__all__ = [
    "assert_notification_count",
    "assert_notification_is_not_queued",
    "assert_notification_is_queued",
    "assert_notification_subject_contains",
    "assert_notification_subject_not_contains",
    "assert_notification_transport_is",
    "assert_notification_transport_is_not",
    "assert_queued_notification_count",
]


def assert_notification_count(
    events: NotificationEvents, count: int, transport: str | None = None
) -> None:
    """Check ``count`` notifications were sent — on ``transport`` only, when given.

    ``events`` is what a :class:`~xtr_notifier.event_listener.NotificationLoggerListener`
    recorded; a notification naming no transport is filed under ``""``.

    Raises:
        AssertionError: When another number was sent.
    """
    _assert_count(events, count, transport, queued=False)


def assert_queued_notification_count(
    events: NotificationEvents, count: int, transport: str | None = None
) -> None:
    """Check ``count`` notifications were queued on a bus — on ``transport`` only, when given.

    Raises:
        AssertionError: When another number was queued.
    """
    _assert_count(events, count, transport, queued=True)


def assert_notification_is_queued(event: MessageEvent) -> None:
    """Check ``event``'s message was queued on a bus rather than sent.

    Raises:
        AssertionError: When it was sent.
    """
    if not event.queued:
        raise AssertionError("The notification is not queued.")


def assert_notification_is_not_queued(event: MessageEvent) -> None:
    """Check ``event``'s message was sent rather than queued.

    Raises:
        AssertionError: When it was queued.
    """
    if event.queued:
        raise AssertionError("The notification is queued.")


def assert_notification_subject_contains(message: MessageInterface, text: str) -> None:
    """Check ``message``'s subject contains ``text``.

    Raises:
        AssertionError: When it does not.
    """
    if text not in message.subject:
        raise AssertionError(
            f'The notification subject "{message.subject}" does not contain "{text}".'
        )


def assert_notification_subject_not_contains(message: MessageInterface, text: str) -> None:
    """Check ``message``'s subject does not contain ``text``.

    Raises:
        AssertionError: When it does.
    """
    if text in message.subject:
        raise AssertionError(f'The notification subject "{message.subject}" contains "{text}".')


def assert_notification_transport_is(message: MessageInterface, transport: str | None) -> None:
    """Check ``message`` names the transport ``transport`` — ``None`` for none.

    Raises:
        AssertionError: When it names another.
    """
    if message.transport != transport:
        raise AssertionError(
            f"The notification transport is {message.transport!r}, not {transport!r}."
        )


def assert_notification_transport_is_not(message: MessageInterface, transport: str | None) -> None:
    """Check ``message`` does not name the transport ``transport``.

    Raises:
        AssertionError: When it does.
    """
    if message.transport == transport:
        raise AssertionError(f"The notification transport is {message.transport!r}.")


def _assert_count(
    events: NotificationEvents, count: int, transport: str | None, *, queued: bool
) -> None:
    """Check ``count`` events for ``transport`` were queued, or sent."""
    found = sum(1 for event in events.get_events(transport) if event.queued is queued)
    if found != count:
        where = "" if transport is None else f' on "{transport}"'
        how = "queued" if queued else "sent"
        raise AssertionError(f"Expected {count} notification(s) {how}{where}, found {found}.")
