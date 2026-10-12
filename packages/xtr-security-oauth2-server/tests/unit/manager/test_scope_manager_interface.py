"""The shipped scope manager satisfies the contract the bridge goes through."""

from __future__ import annotations

from xtr_security_oauth2_server.manager.in_memory.scope_manager import ScopeManager
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface


def test_the_in_memory_manager_satisfies_it() -> None:
    assert isinstance(ScopeManager(("read",)), ScopeManagerInterface)
