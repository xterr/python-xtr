"""Checks on the emails an application sent or queued, read from what a listener recorded."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from xtr_mailer.event import MessageEvent, MessageEvents

__all__ = [
    "assert_email_count",
    "assert_email_is_not_queued",
    "assert_email_is_queued",
    "assert_queued_email_count",
]


def assert_email_count(
    events: MessageEvents, expected_count: int, transport_name: str | None = None
) -> None:
    """Check ``expected_count`` emails were sent — through ``transport_name`` only, when given.

    ``events`` is what a :class:`~xtr_mailer.event_listener.MessageLoggerListener` recorded; a
    transport goes by the name it gives itself, ``null://`` or ``smtp://mail.example.com``.

    Raises:
        AssertionError: When another number was sent.
    """
    _assert_count(events, expected_count, transport_name, queued=False)


def assert_queued_email_count(
    events: MessageEvents, expected_count: int, transport_name: str | None = None
) -> None:
    """Check ``expected_count`` emails were queued on a message bus, for ``transport_name``.

    ``transport_name`` left out, every email queued counts.

    Raises:
        AssertionError: When another number was queued.
    """
    _assert_count(events, expected_count, transport_name, queued=True)


def assert_email_is_queued(event: MessageEvent) -> None:
    """Check ``event``'s email was queued on a message bus rather than sent.

    Raises:
        AssertionError: When it was sent.
    """
    if not event.is_queued():
        _fail("the Email is queued")


def assert_email_is_not_queued(event: MessageEvent) -> None:
    """Check ``event``'s email was sent rather than queued.

    Raises:
        AssertionError: When it was queued.
    """
    if event.is_queued():
        _fail("the Email is not queued")


def _assert_count(
    events: MessageEvents, expected_count: int, transport_name: str | None, *, queued: bool
) -> None:
    """Check ``expected_count`` of the emails for ``transport_name`` were queued, or sent."""
    found = sum(1 for event in events.get_events(transport_name) if event.is_queued() is queued)
    if found != expected_count:
        how = "queued" if queued else "sent"
        where = f"{transport_name} " if transport_name else ""
        _fail(f'the Transport {where}has {how} "{expected_count}" emails ({found} {how})')


def _fail(expectation: str) -> NoReturn:
    """Raise an :class:`AssertionError` saying ``expectation`` did not hold."""
    raise AssertionError(f"Failed asserting that {expectation}.")
