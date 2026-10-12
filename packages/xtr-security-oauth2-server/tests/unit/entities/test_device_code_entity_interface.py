"""The device-code contract is runtime-checkable."""

from __future__ import annotations

from tests.support.entities import AccessToken, DeviceCode
from xtr_security_oauth2_server.entities.device_code_entity_interface import (
    DeviceCodeEntityInterface,
)


def test_a_device_code_entity_satisfies_the_contract() -> None:
    code: DeviceCodeEntityInterface = DeviceCode()
    assert isinstance(code, DeviceCodeEntityInterface)


def test_a_token_carrying_no_user_code_does_not_satisfy_it() -> None:
    assert not isinstance(AccessToken(), DeviceCodeEntityInterface)
