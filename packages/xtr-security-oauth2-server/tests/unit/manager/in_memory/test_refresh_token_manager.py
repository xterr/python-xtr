"""Refresh tokens kept in this process, revoked by exactly one caller."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, refresh_token_model
from xtr_security_oauth2_server.manager.in_memory.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)

pytestmark = pytest.mark.anyio


def _manager() -> RefreshTokenManager:
    return RefreshTokenManager(MockClock(NOW))


def test_it_declares_the_refresh_token_manager_contract() -> None:
    assert RefreshTokenManagerInterface in RefreshTokenManager.__mro__


async def test_it_finds_a_token_it_stored() -> None:
    manager = _manager()
    token = refresh_token_model()

    await manager.save(token)

    assert await manager.find("rt-1") is token


async def test_it_finds_nothing_under_an_unknown_identifier() -> None:
    assert await _manager().find("nope") is None


async def test_storing_the_same_identifier_again_replaces_what_was_stored() -> None:
    manager = _manager()
    await manager.save(refresh_token_model())
    replacement = refresh_token_model(expiry=EARLIER)

    await manager.save(replacement)

    assert await manager.find("rt-1") is replacement


async def test_it_forgets_the_tokens_that_have_expired() -> None:
    manager = _manager()
    await manager.save(refresh_token_model("expired", EARLIER))
    await manager.save(refresh_token_model("alive", LATER))

    cleared = await manager.clear_expired()

    assert cleared == 1
    assert await manager.find("expired") is None
    assert await manager.find("alive") is not None


async def test_the_first_caller_to_revoke_a_token_is_told_it_did() -> None:
    manager = _manager()
    await manager.save(refresh_token_model())

    assert await manager.revoke("rt-1") is True


async def test_the_second_caller_to_revoke_the_same_token_is_told_it_did_not() -> None:
    manager = _manager()
    await manager.save(refresh_token_model())
    _ = await manager.revoke("rt-1")

    assert await manager.revoke("rt-1") is False


async def test_revoking_marks_the_stored_token_revoked() -> None:
    manager = _manager()
    token = refresh_token_model()
    await manager.save(token)

    _ = await manager.revoke("rt-1")

    assert token.is_revoked() is True


async def test_revoking_an_unknown_token_is_told_it_revoked_nothing() -> None:
    assert await _manager().revoke("nope") is False
