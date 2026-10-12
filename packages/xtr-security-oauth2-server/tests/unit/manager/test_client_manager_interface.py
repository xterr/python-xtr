"""The shipped client manager satisfies the contract the bridge goes through."""

from __future__ import annotations

from tests.support.dispatcher import RecordingEventDispatcher
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.in_memory.client_manager import ClientManager


def test_the_in_memory_manager_satisfies_it() -> None:
    assert isinstance(ClientManager(RecordingEventDispatcher()), ClientManagerInterface)
