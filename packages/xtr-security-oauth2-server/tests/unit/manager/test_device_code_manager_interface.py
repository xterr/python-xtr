"""The shipped device-code manager satisfies the contract the bridge goes through."""

from __future__ import annotations

from xtr_clock import MockClock

from tests.support.models import NOW
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.device_code_manager import DeviceCodeManager


def test_the_in_memory_manager_satisfies_it() -> None:
    assert isinstance(DeviceCodeManager(MockClock(NOW)), DeviceCodeManagerInterface)
