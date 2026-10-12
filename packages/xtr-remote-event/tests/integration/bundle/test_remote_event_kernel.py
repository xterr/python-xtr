"""End-to-end: an application listing RemoteEventBundle consumes what its bus carries."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_messenger import HandlersFailedError, MessageBusInterface

from tests.fixtures.app_consumers.services import OTHER, TEST, BothSourcesConsumer
from xtr_remote_event import RemoteEvent
from xtr_remote_event.exception import LogicError
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_consumers"
DUPLICATE_APP = "tests.fixtures.app_duplicate_consumers"


async def test_one_consumer_receives_under_every_name_it_declared() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        bus = await booted.container.get(MessageBusInterface)
        first = RemoteEvent(TEST, "evt_1", {"amount": 500})
        second = RemoteEvent(OTHER, "evt_2", {"amount": 700})

        _ = await bus.dispatch(ConsumeRemoteEventMessage(TEST, first))
        _ = await bus.dispatch(ConsumeRemoteEventMessage(OTHER, second))

        consumer = await booted.container.get(BothSourcesConsumer)
        assert consumer.consumed == [first, second]


async def test_a_type_nothing_consumes_fails_the_dispatch() -> None:
    async with await Kernel(APP, env="test").boot() as booted:
        bus = await booted.container.get(MessageBusInterface)

        with pytest.raises(HandlersFailedError) as caught:
            _ = await bus.dispatch(
                ConsumeRemoteEventMessage("mailgun", RemoteEvent("mailgun", "evt_1", {}))
            )

    (failure,) = caught.value.errors.values()
    assert isinstance(failure, LogicError)
    assert str(failure) == 'Unable to find a consumer for message of type "mailgun".'


async def test_two_consumers_claiming_one_name_fail_the_build() -> None:
    with pytest.raises(LogicError) as caught:
        async with await Kernel(DUPLICATE_APP, env="test").boot():
            pass

    assert str(caught.value) == (
        'The remote event consumer name "test" is declared by both FirstConsumer and '
        "SecondConsumer."
    )
