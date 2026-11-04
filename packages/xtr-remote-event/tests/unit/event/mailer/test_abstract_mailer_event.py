from __future__ import annotations

import dataclasses
import inspect
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from xtr_remote_event import RemoteEvent
from xtr_remote_event.event.mailer import AbstractMailerEvent

if TYPE_CHECKING:
    from collections.abc import Callable

_DATE = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _SuppressedEvent(AbstractMailerEvent):
    """A report of the test's own, standing for any type derived from the base."""


def _build(event_type: Callable[..., object], *args: object, **kwargs: object) -> object:
    # Taking an untyped callable keeps the type checkers out of the way. They refuse the
    # call on sight, and what is being tested here is that so does the runtime.
    return event_type(*args, **kwargs)


def test_it_cannot_be_built_itself() -> None:
    with pytest.raises(TypeError) as caught:
        _ = AbstractMailerEvent("delivered", "evt_1", {}, date=_DATE)

    assert str(caught.value) == (
        '"AbstractMailerEvent" is abstract: build a "MailerDeliveryEvent" or a '
        '"MailerEngagementEvent" instead.'
    )


def test_a_type_derived_from_it_builds_a_remote_event() -> None:
    event = _SuppressedEvent("suppressed", "evt_1", {}, date=_DATE)

    assert isinstance(event, RemoteEvent)


def test_what_it_adds_is_empty_unless_given() -> None:
    event = _SuppressedEvent("suppressed", "evt_1", {}, date=_DATE)

    assert (event.recipient_email, event.metadata, event.tags) == ("", {}, ())


def test_what_it_adds_is_given_by_keyword() -> None:
    parameters = inspect.signature(_SuppressedEvent).parameters.values()

    assert [
        parameter.name
        for parameter in parameters
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ] == ["date", "recipient_email", "metadata", "tags"]


def test_a_report_without_a_date_is_refused() -> None:
    with pytest.raises(TypeError, match="'date'"):
        _ = _build(_SuppressedEvent, "suppressed", "evt_1", {})
