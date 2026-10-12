"""The device-code entity, carrying the user code and the polling state."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.entities.device_code_entity_interface import (
    DeviceCodeEntityInterface,
)
from xtr_security_oauth2_server.entity.client import Client
from xtr_security_oauth2_server.entity.device_code import DeviceCode


def _device_code() -> DeviceCode:
    client = Client()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri([])
    client.set_confidential(False)

    code = DeviceCode()
    code.set_identifier("dc-identifier-1")
    code.set_client(client)
    code.set_expiry_date_time(datetime(2026, 3, 4, 5, 16, 7, tzinfo=UTC))
    code.set_user_code("BCDFGHJK")
    code.set_verification_uri("https://authorization.example.com/device")

    return code


def test_it_satisfies_the_device_code_contract() -> None:
    assert DeviceCodeEntityInterface in DeviceCode.__mro__
    assert isinstance(_device_code(), DeviceCodeEntityInterface)


def test_it_is_built_with_no_arguments_so_a_repository_can_mint_one() -> None:
    assert DeviceCode().get_user_approved() is False


def test_it_reports_the_short_code_its_owner_types_in() -> None:
    assert _device_code().get_user_code() == "BCDFGHJK"


def test_it_builds_the_uri_that_pre_fills_that_code() -> None:
    expected = "https://authorization.example.com/device?user_code=BCDFGHJK"

    assert _device_code().get_verification_uri_complete() == expected


def test_its_reading_holds_neither_the_user_code_nor_the_identifier_in_full() -> None:
    reading = repr(_device_code())

    assert "BCDFGHJK" not in reading
    assert reading == "DeviceCode(identifier='dc-ident...')"
