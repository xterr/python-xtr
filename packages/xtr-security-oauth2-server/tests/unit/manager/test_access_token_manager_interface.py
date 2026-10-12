"""Both shipped access-token managers satisfy the contract the bridge goes through."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.models import NOW
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import (
    AccessTokenManager as InMemoryAccessTokenManager,
)
from xtr_security_oauth2_server.manager.null.access_token_manager import (
    AccessTokenManager as NullAccessTokenManager,
)


def test_the_in_memory_manager_satisfies_it() -> None:
    assert isinstance(InMemoryAccessTokenManager(MockClock(NOW)), AccessTokenManagerInterface)


def test_the_manager_that_stores_nothing_satisfies_it() -> None:
    assert isinstance(NullAccessTokenManager(), AccessTokenManagerInterface)
