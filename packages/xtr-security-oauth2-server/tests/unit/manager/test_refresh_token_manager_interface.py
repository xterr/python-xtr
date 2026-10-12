"""The shipped refresh-token manager satisfies the contract the bridge goes through."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.models import NOW
from xtr_security_oauth2_server.manager.in_memory.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)


def test_the_in_memory_manager_satisfies_it() -> None:
    assert isinstance(RefreshTokenManager(MockClock(NOW)), RefreshTokenManagerInterface)
