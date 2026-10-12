from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_remote_event import ConsumerInterface

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent


@final
class _Consumer:
    """Answers for the events of one source, doing nothing with them."""

    async def consume(self, event: RemoteEvent) -> None:
        """Take the event, as a consumer does."""
        del event


@final
class _WithoutConsume:
    """Takes events under another name, so it is not a consumer."""

    async def handle(self, event: RemoteEvent) -> None:
        """Take the event under a name the contract does not name."""
        del event


def test_a_consumer_with_the_method_satisfies_the_contract() -> None:
    consumer: ConsumerInterface = _Consumer()

    assert isinstance(consumer, ConsumerInterface)


def test_a_class_without_the_method_does_not_satisfy_it() -> None:
    assert not isinstance(_WithoutConsume(), ConsumerInterface)
