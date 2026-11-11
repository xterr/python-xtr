from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

from xtr_ai.exception import InvalidConfigurationError
from xtr_ai.in_memory_run_control import InMemoryRunControl
from xtr_ai.run_control_interface import RunControlInterface
from xtr_ai.testing.run_control_contract import CONTRACT_POLL_INTERVAL, RunControlContract

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_clock import MockClock


class TestInMemoryRunControl(RunControlContract):
    @override
    @asynccontextmanager
    async def build(self, clock: MockClock) -> AsyncGenerator[InMemoryRunControl]:
        yield InMemoryRunControl(clock=clock, cancel_poll_interval=CONTRACT_POLL_INTERVAL)


def test_it_is_a_run_control() -> None:
    assert isinstance(InMemoryRunControl(), RunControlInterface)


def test_the_poll_interval_must_be_positive() -> None:
    with pytest.raises(InvalidConfigurationError, match="cancel_poll_interval"):
        _ = InMemoryRunControl(cancel_poll_interval=0)


def test_the_heartbeat_interval_must_be_positive() -> None:
    with pytest.raises(InvalidConfigurationError, match="heartbeat_interval must"):
        _ = InMemoryRunControl(heartbeat_interval=timedelta(0))


def test_a_run_goes_stale_only_after_missing_a_heartbeat() -> None:
    with pytest.raises(InvalidConfigurationError, match="stale_after"):
        _ = InMemoryRunControl(stale_after=timedelta(seconds=5))


def test_a_run_cannot_go_stale_between_two_polls() -> None:
    with pytest.raises(InvalidConfigurationError, match="cancel_poll_interval"):
        _ = InMemoryRunControl(cancel_poll_interval=120)
