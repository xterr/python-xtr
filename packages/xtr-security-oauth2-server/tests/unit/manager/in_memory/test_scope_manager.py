"""The scopes this deployment knows, held in this process."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.manager.in_memory.scope_manager import ScopeManager
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.value_object.scope import Scope

pytestmark = pytest.mark.anyio


def test_it_declares_the_scope_manager_contract() -> None:
    assert ScopeManagerInterface in ScopeManager.__mro__


async def test_it_knows_the_scopes_it_was_built_with() -> None:
    manager = ScopeManager(("read", "write"))

    assert await manager.find("read") == Scope("read")


async def test_it_knows_nothing_when_built_with_nothing() -> None:
    assert await ScopeManager().find("read") is None


async def test_it_does_not_know_a_scope_nobody_made_available() -> None:
    manager = ScopeManager(("read",))

    assert await manager.find("write") is None


async def test_it_knows_a_scope_it_was_handed_afterwards() -> None:
    manager = ScopeManager()

    await manager.save(Scope("write"))

    assert await manager.find("write") == Scope("write")
