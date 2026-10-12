from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config

from xtr_remote_event.bundle import RemoteEventBundle
from xtr_remote_event.bundle._declared_consumers import DeclaredConsumers
from xtr_remote_event.bundle.remote_event_bundle import _consumer_locator
from xtr_remote_event.exception import LogicError

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(RemoteEventBundle)


async def test_the_consumer_locator_is_refused_before_the_bundle_booted() -> None:
    build = _consumer_locator(RemoteEventBundle(), DeclaredConsumers())

    with pytest.raises(LogicError, match="has no container"):
        _ = await build()
