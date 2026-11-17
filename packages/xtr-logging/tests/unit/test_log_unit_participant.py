"""Every unit of work the container opens is a log unit of its own."""

from __future__ import annotations

import asyncio

import pytest
from xtr_dependency_injection import unit_of_work
from xtr_dependency_injection.integration.wireup import create_container
from xtr_dependency_injection.runtime.wireup_container import WireupContainer
from xtr_logging_contracts import Level
from xtr_service_contracts import UnitParticipantInterface

from tests.fixtures import app_log_units
from tests.fixtures.app_log_units import HANDLER, SPY, Resource
from tests.support.records import make_record
from xtr_logging import TestHandler
from xtr_logging.bundle import LoggingBundle
from xtr_logging.handler.fingers_crossed_handler import FingersCrossedHandler
from xtr_logging.log_unit import in_unit
from xtr_logging.log_unit_participant import LogUnitParticipant

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fresh_handler() -> None:
    SPY.clear()
    HANDLER.clear()


def test_it_is_a_unit_participant() -> None:
    assert isinstance(LogUnitParticipant(), UnitParticipantInterface)


def test_a_unit_it_began_is_open_until_it_ends() -> None:
    participant = LogUnitParticipant()

    token = participant.unit_began()
    opened = in_unit()
    participant.unit_ended(token)

    assert opened
    assert not in_unit()


async def test_two_concurrent_messages_flush_only_their_own_records() -> None:
    participant = LogUnitParticipant()
    spy = TestHandler()
    handler = FingersCrossedHandler(spy, activation_strategy=Level.ERROR)
    a_logged, b_failed = asyncio.Event(), asyncio.Event()

    async def message_a() -> None:
        token = participant.unit_began()
        _ = handler.handle(make_record(Level.DEBUG, "A secret debug"))
        a_logged.set()
        _ = await b_failed.wait()
        participant.unit_ended(token)

    async def message_b() -> None:
        token = participant.unit_began()
        _ = await a_logged.wait()
        _ = handler.handle(make_record(Level.DEBUG, "B secret debug"))
        _ = handler.handle(make_record(Level.ERROR, "B failed"))
        b_failed.set()
        participant.unit_ended(token)

    _ = await asyncio.gather(message_a(), message_b())

    assert [record.message for record in spy.records] == ["B secret debug", "B failed"]


def _container() -> WireupContainer:
    return WireupContainer(create_container([LoggingBundle], scan=[app_log_units.__name__]))


async def test_a_record_logged_during_scope_teardown_lands_in_the_messages_own_unit() -> None:
    container = _container()
    a_started, b_started = asyncio.Event(), asyncio.Event()

    async def message(name: str, started: asyncio.Event, other: asyncio.Event) -> None:
        async with unit_of_work(container, join=False) as unit:
            (await unit.get(Resource)).name = name
            _ = HANDLER.handle(make_record(Level.DEBUG, f"{name} debug"))
            started.set()
            _ = await other.wait()
            if name == "A":
                _ = HANDLER.handle(make_record(Level.ERROR, "A failed"))

    _ = await asyncio.gather(message("A", a_started, b_started), message("B", b_started, a_started))

    assert [record.message for record in SPY.records] == ["A debug", "A failed", "A teardown"]


async def test_a_reset_from_the_host_context_leaves_message_units_alone() -> None:
    container = _container()
    buffered, reset = asyncio.Event(), asyncio.Event()

    async def message() -> None:
        async with unit_of_work(container, join=False):
            _ = HANDLER.handle(make_record(Level.DEBUG, "message debug"))
            buffered.set()
            _ = await reset.wait()
            _ = HANDLER.handle(make_record(Level.ERROR, "message failed"))

    handling = asyncio.create_task(message())
    _ = await buffered.wait()
    # What a worker does between messages, from the command hosting it.
    await HANDLER.reset()
    reset.set()
    await handling

    assert [record.message for record in SPY.records] == ["message debug", "message failed"]


async def test_the_logging_bundle_tells_the_participant_of_every_unit() -> None:
    container = _container()

    async with unit_of_work(container):
        opened = in_unit()

    assert opened
    assert not in_unit()
