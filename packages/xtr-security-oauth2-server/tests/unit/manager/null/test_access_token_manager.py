"""The manager for a deployment that stores no access token at all."""

from __future__ import annotations

import pytest

from tests.support.models import access_token_model
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.null.access_token_manager import AccessTokenManager

pytestmark = pytest.mark.anyio


def test_it_declares_the_access_token_manager_contract() -> None:
    assert AccessTokenManagerInterface in AccessTokenManager.__mro__


async def test_it_finds_nothing_whatever_it_was_handed() -> None:
    manager = AccessTokenManager()

    await manager.save(access_token_model())

    assert await manager.find("at-1") is None


async def test_it_clears_nothing() -> None:
    assert await AccessTokenManager().clear_expired() == 0
