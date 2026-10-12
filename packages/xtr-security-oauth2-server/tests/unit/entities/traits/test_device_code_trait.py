"""A device code carries the user code, and builds the URI that pre-fills it."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.support.entities import DeviceCode

_POLLED_AT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def test_it_hands_back_the_user_code_it_was_given() -> None:
    code = DeviceCode()
    code.set_user_code("BCDFGHJK")

    assert code.get_user_code() == "BCDFGHJK"


def test_it_hands_back_the_verification_uri_it_was_given() -> None:
    code = DeviceCode()
    code.set_verification_uri("https://authorization.example.com/device")

    assert code.get_verification_uri() == "https://authorization.example.com/device"


def test_the_complete_uri_carries_the_user_code_as_a_query_parameter() -> None:
    code = DeviceCode()
    code.set_verification_uri("https://authorization.example.com/device")
    code.set_user_code("BCDFGHJK")

    assert code.get_verification_uri_complete() == (
        "https://authorization.example.com/device?user_code=BCDFGHJK"
    )


def test_the_complete_uri_percent_encodes_a_user_code_holding_reserved_characters() -> None:
    code = DeviceCode()
    code.set_verification_uri("https://authorization.example.com/device")
    code.set_user_code("A B&C=D")

    assert code.get_verification_uri_complete() == (
        "https://authorization.example.com/device?user_code=A%20B%26C%3DD"
    )


def test_the_complete_uri_keeps_a_query_the_verification_uri_already_carried() -> None:
    code = DeviceCode()
    code.set_verification_uri("https://authorization.example.com/device?locale=ro")
    code.set_user_code("BCDFGHJK")

    assert code.get_verification_uri_complete() == (
        "https://authorization.example.com/device?locale=ro&user_code=BCDFGHJK"
    )


def test_it_has_not_been_polled_until_it_is() -> None:
    assert DeviceCode().get_last_polled_at() is None


def test_it_hands_back_the_poll_it_was_told_about() -> None:
    code = DeviceCode()
    code.set_last_polled_at(_POLLED_AT)

    assert code.get_last_polled_at() == _POLLED_AT


def test_it_asks_to_be_polled_every_five_seconds_by_default() -> None:
    assert DeviceCode().get_interval() == 5


def test_it_hands_back_the_interval_it_was_given() -> None:
    code = DeviceCode()
    code.set_interval(10)

    assert code.get_interval() == 10


def test_it_is_not_approved_until_the_user_approves_it() -> None:
    assert DeviceCode().get_user_approved() is False


def test_it_hands_back_the_approval_it_was_given() -> None:
    code = DeviceCode()
    code.set_user_approved(True)

    assert code.get_user_approved() is True


def test_it_keeps_the_complete_uri_out_of_the_authorization_response_by_default() -> None:
    assert DeviceCode().get_verification_uri_complete_in_auth_response() is False


def test_it_hands_back_the_authorization_response_choice_it_was_given() -> None:
    code = DeviceCode()
    code.set_verification_uri_complete_in_auth_response(True)

    assert code.get_verification_uri_complete_in_auth_response() is True


def test_its_reading_holds_neither_the_user_code_nor_the_verification_uri() -> None:
    code = DeviceCode()
    code.set_identifier("a1b2c3d4e5f60718293a4b5c6d7e8f9012345678")
    code.set_user_code("BCDFGHJK")
    code.set_verification_uri("https://authorization.example.com/device")

    reading = repr(code)

    assert "BCDFGHJK" not in reading
    assert "authorization.example.com" not in reading
