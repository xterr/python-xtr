from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel, ServiceLocator
from xtr_dependency_injection.testing import assert_zero_config

from tests.fixtures.app_consumers.services import OTHER, TEST, BothSourcesConsumer
from xtr_remote_event.bundle import RemoteEventBundle
from xtr_remote_event.bundle.remote_event_bundle import _consumer_locator
from xtr_remote_event.consumer import ConsumerInterface

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(RemoteEventBundle)


async def test_the_consumer_locator_serves_the_names_the_container_locator_holds() -> None:
    # Built from the locator the container injects, never from the container itself.
    async with await Kernel("tests.fixtures.app_consumers", env="test").boot() as booted:
        consumers = await booted.container.get(ServiceLocator[ConsumerInterface])

        locator = _consumer_locator(consumers)

        assert locator.has(TEST)
        assert locator.has(OTHER)
        assert not locator.has("stripe")
        assert isinstance(await locator.get(TEST), BothSourcesConsumer)
