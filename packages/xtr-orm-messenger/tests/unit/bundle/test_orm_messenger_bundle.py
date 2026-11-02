from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config

from xtr_orm_messenger.bundle import OrmMessengerBundle

pytestmark = pytest.mark.anyio


async def test_zero_config_builds_boots_and_shuts_down() -> None:
    await assert_zero_config(OrmMessengerBundle)
