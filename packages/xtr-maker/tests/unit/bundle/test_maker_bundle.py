"""Unit tests for :class:`xtr_maker.bundle.MakerBundle`."""

from __future__ import annotations

import pytest
from xtr_dependency_injection.testing import assert_zero_config

from xtr_maker.bundle import MakerBundle

pytestmark = pytest.mark.anyio


async def test_zero_config_boots_and_shuts_down() -> None:
    await assert_zero_config(MakerBundle)
