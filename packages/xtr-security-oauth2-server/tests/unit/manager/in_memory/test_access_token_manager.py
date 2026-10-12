"""Access tokens kept in this process, and forgotten when they expire."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, access_token_model
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import AccessTokenManager

pytestmark = pytest.mark.anyio


def _manager(*, persist_access_token: bool = True) -> AccessTokenManager:
    return AccessTokenManager(MockClock(NOW), persist_access_token)


def test_it_declares_the_access_token_manager_contract() -> None:
    assert AccessTokenManagerInterface in AccessTokenManager.__mro__


async def test_it_finds_a_token_it_stored() -> None:
    manager = _manager()
    token = access_token_model()

    await manager.save(token)

    assert await manager.find("at-1") is token


async def test_it_finds_nothing_under_an_unknown_identifier() -> None:
    assert await _manager().find("nope") is None


async def test_storing_the_same_identifier_again_replaces_what_was_stored() -> None:
    manager = _manager()
    await manager.save(access_token_model())
    replacement = access_token_model(scopes=("read",))

    await manager.save(replacement)

    assert await manager.find("at-1") is replacement


async def test_it_forgets_the_tokens_that_have_expired() -> None:
    manager = _manager()
    await manager.save(access_token_model("expired", EARLIER))
    await manager.save(access_token_model("alive", LATER))

    cleared = await manager.clear_expired()

    assert cleared == 1
    assert await manager.find("expired") is None
    assert await manager.find("alive") is not None


async def test_a_token_expiring_exactly_now_is_kept() -> None:
    manager = _manager()
    await manager.save(access_token_model("on-the-dot", NOW))

    assert await manager.clear_expired() == 0


async def test_it_stores_nothing_when_access_tokens_are_not_persisted() -> None:
    manager = _manager(persist_access_token=False)

    await manager.save(access_token_model())

    assert await manager.find("at-1") is None


async def test_it_clears_nothing_when_access_tokens_are_not_persisted() -> None:
    manager = _manager(persist_access_token=False)
    await manager.save(access_token_model("expired", EARLIER))

    assert await manager.clear_expired() == 0
