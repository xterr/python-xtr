from __future__ import annotations

import pytest
from xtr_messenger import default_registry

from tests.support.consumers import ConsumerProvider, NotAConsumer, RecordingConsumer
from xtr_remote_event import RemoteEvent
from xtr_remote_event.consumer import ConsumerLocator
from xtr_remote_event.exception import LogicError
from xtr_remote_event.messenger import ConsumeRemoteEventHandler, ConsumeRemoteEventMessage


def test_it_is_declared_as_the_handler_of_the_message() -> None:
    declared = default_registry().handlers_for(ConsumeRemoteEventMessage)

    assert [d.handler for d in declared] == [ConsumeRemoteEventHandler]


@pytest.mark.anyio
async def test_it_hands_the_event_to_the_consumer_of_the_messages_type() -> None:
    stripe, mailgun = RecordingConsumer(), RecordingConsumer()
    handler = ConsumeRemoteEventHandler(ConsumerLocator({"stripe": stripe, "mailgun": mailgun}))
    event = RemoteEvent("stripe", "evt_1", {"amount": 500})

    await handler(ConsumeRemoteEventMessage("stripe", event))

    assert stripe.consumed == [event]
    assert mailgun.consumed == []


@pytest.mark.anyio
async def test_it_refuses_a_type_no_consumer_is_registered_for() -> None:
    handler = ConsumeRemoteEventHandler(ConsumerLocator({}))

    with pytest.raises(LogicError) as caught:
        await handler(ConsumeRemoteEventMessage("mailgun", RemoteEvent("mailgun", "evt_1", {})))

    assert str(caught.value) == 'Unable to find a consumer for message of type "mailgun".'


@pytest.mark.anyio
async def test_it_refuses_something_registered_that_consumes_nothing() -> None:
    handler = ConsumeRemoteEventHandler(
        ConsumerLocator(ConsumerProvider({"stripe": NotAConsumer()}))
    )

    with pytest.raises(LogicError) as caught:
        await handler(ConsumeRemoteEventMessage("stripe", RemoteEvent("stripe", "evt_1", {})))

    assert str(caught.value) == (
        'The consumer "NotAConsumer" for message of type "stripe" must implement ConsumerInterface.'
    )
