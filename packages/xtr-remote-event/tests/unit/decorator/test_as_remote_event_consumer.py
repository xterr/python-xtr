from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_remote_event import as_remote_event_consumer
from xtr_remote_event.decorator import remote_event_consumers_declared_on
from xtr_remote_event.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent


class _Consumer:
    """What the decorator asks for: a class that can take an event."""

    async def consume(self, event: RemoteEvent) -> None:
        """Take the event, as a consumer does."""
        del event


class _WithoutConsume:
    """Named as a consumer by mistake: there is nothing on it to hand an event to."""


def test_it_records_the_name_it_was_given() -> None:
    @as_remote_event_consumer("stripe")
    class Consumer(_Consumer):
        pass

    assert remote_event_consumers_declared_on(Consumer) == ("stripe",)


def test_stacked_decorators_record_every_name_in_the_order_they_run() -> None:
    @as_remote_event_consumer("stripe")
    @as_remote_event_consumer("mailgun")
    class Consumer(_Consumer):
        pass

    assert remote_event_consumers_declared_on(Consumer) == ("mailgun", "stripe")


def test_a_consumer_without_a_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = as_remote_event_consumer("")

    assert str(refused.value) == "A remote event consumer needs a non-empty name."


def test_a_class_that_cannot_consume_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = as_remote_event_consumer("stripe")(_WithoutConsume)

    assert (
        str(refused.value) == "_WithoutConsume must define consume() to be a remote event consumer."
    )


def test_an_undecorated_class_declares_nothing() -> None:
    assert remote_event_consumers_declared_on(_Consumer) == ()


def test_a_subclass_does_not_inherit_what_its_parent_declared() -> None:
    @as_remote_event_consumer("stripe")
    class Parent(_Consumer):
        pass

    class Child(Parent):
        pass

    assert remote_event_consumers_declared_on(Parent) == ("stripe",)
    assert remote_event_consumers_declared_on(Child) == ()
