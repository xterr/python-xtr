"""The shipped device-code model satisfies the contract a manager stores it through."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface


def test_the_shipped_model_satisfies_it() -> None:
    code = DeviceCode(
        "dc-1",
        datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC),
        Client("C", "client-1", None),
        None,
        (),
        "BCDFGHJK",
        user_approved=False,
        verification_uri="https://authorization.example.com/device",
        last_polled_at=None,
        interval=5,
    )

    assert isinstance(code, DeviceCodeInterface)
