"""Authorization codes kept in this process, and forgotten when they expire."""

from __future__ import annotations

import pytest
from xtr_clock import MockClock

from tests.support.models import EARLIER, LATER, NOW, authorization_code_model
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.authorization_code_manager import (
    AuthorizationCodeManager,
)

pytestmark = pytest.mark.anyio


def _manager() -> AuthorizationCodeManager:
    return AuthorizationCodeManager(MockClock(NOW))


def test_it_declares_the_authorization_code_manager_contract() -> None:
    assert AuthorizationCodeManagerInterface in AuthorizationCodeManager.__mro__


async def test_it_finds_a_code_it_stored() -> None:
    manager = _manager()
    code = authorization_code_model()

    await manager.save(code)

    assert await manager.find("ac-1") is code


async def test_it_finds_nothing_under_an_unknown_identifier() -> None:
    assert await _manager().find("nope") is None


async def test_storing_the_same_identifier_again_replaces_what_was_stored() -> None:
    manager = _manager()
    await manager.save(authorization_code_model())
    replacement = authorization_code_model(scopes=("read",))

    await manager.save(replacement)

    assert await manager.find("ac-1") is replacement


async def test_it_forgets_the_codes_that_have_expired() -> None:
    manager = _manager()
    await manager.save(authorization_code_model("expired", EARLIER))
    await manager.save(authorization_code_model("alive", LATER))

    cleared = await manager.clear_expired()

    assert cleared == 1
    assert await manager.find("expired") is None
    assert await manager.find("alive") is not None


async def test_a_code_expiring_exactly_now_is_kept() -> None:
    manager = _manager()
    await manager.save(authorization_code_model("on-the-dot", NOW))

    assert await manager.clear_expired() == 0
