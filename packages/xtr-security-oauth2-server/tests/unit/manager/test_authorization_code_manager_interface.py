"""The shipped authorization-code manager satisfies the contract the bridge goes through."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.models import NOW
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.authorization_code_manager import (
    AuthorizationCodeManager,
)


def test_the_in_memory_manager_satisfies_it() -> None:
    manager = AuthorizationCodeManager(MockClock(NOW))

    assert isinstance(manager, AuthorizationCodeManagerInterface)
