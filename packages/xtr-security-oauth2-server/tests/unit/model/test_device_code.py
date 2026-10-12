"""A stored device code carries the user code, the approval and the polling state."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.device_code import DeviceCode
from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface
from xtr_security_oauth2_server.value_object.scope import Scope

_EXPIRY = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_POLLED_AT = datetime(2026, 3, 4, 5, 0, 0, tzinfo=UTC)


def _device_code(
    *,
    user_identifier: str | None = "user-1",
    user_approved: bool = False,
    last_polled_at: datetime | None = None,
    include_verification_uri_complete: bool = False,
) -> DeviceCode:
    return DeviceCode(
        "dc-identifier-1",
        _EXPIRY,
        Client("Test client", "client-1", None),
        user_identifier,
        (Scope("read"),),
        "BCDFGHJK",
        user_approved,
        "https://authorization.example.com/device",
        last_polled_at,
        5,
        include_verification_uri_complete=include_verification_uri_complete,
    )


def test_it_declares_the_device_code_contract() -> None:
    assert DeviceCodeInterface in DeviceCode.__mro__


def test_it_reads_as_its_identifier() -> None:
    assert str(_device_code()) == "dc-identifier-1"


def test_it_reports_the_identifier_it_was_stored_under() -> None:
    assert _device_code().get_identifier() == "dc-identifier-1"


def test_it_reports_when_it_stops_being_accepted() -> None:
    assert _device_code().get_expiry() == _EXPIRY


def test_it_reports_the_client_the_device_acts_for() -> None:
    assert _device_code().get_client().get_identifier() == "client-1"


def test_it_reports_the_scopes_asked_for() -> None:
    assert _device_code().get_scopes() == (Scope("read"),)


def test_it_reports_the_short_code_its_owner_types_in() -> None:
    assert _device_code().get_user_code() == "BCDFGHJK"


def test_it_reports_where_its_owner_goes_to_type_that_code() -> None:
    assert _device_code().get_verification_uri() == "https://authorization.example.com/device"


def test_it_names_no_resource_owner_before_anyone_approves_it() -> None:
    assert _device_code(user_identifier=None).get_user_identifier() is None


def test_its_resource_owner_is_recorded_when_one_approves_it() -> None:
    code = _device_code(user_identifier=None)

    _ = code.set_user_identifier("user-2")

    assert code.get_user_identifier() == "user-2"


def test_it_is_unapproved_until_its_owner_approves_it() -> None:
    assert _device_code().get_user_approved() is False


def test_its_approval_is_recorded() -> None:
    code = _device_code()

    _ = code.set_user_approved(True)

    assert code.get_user_approved() is True


def test_it_was_never_polled_when_stored() -> None:
    assert _device_code().get_last_polled_at() is None


def test_its_last_poll_is_recorded() -> None:
    code = _device_code()

    _ = code.set_last_polled_at(_POLLED_AT)

    assert code.get_last_polled_at() == _POLLED_AT


def test_it_reports_how_long_the_device_is_asked_to_wait_between_polls() -> None:
    assert _device_code().get_interval() == 5


def test_it_keeps_the_pre_filled_uri_out_of_the_response_unless_asked() -> None:
    assert _device_code().get_include_verification_uri_complete() is False


def test_it_remembers_that_the_pre_filled_uri_was_asked_for() -> None:
    code = _device_code(include_verification_uri_complete=True)

    assert code.get_include_verification_uri_complete() is True


def test_it_is_not_revoked_when_stored() -> None:
    assert _device_code().is_revoked() is False


def test_it_is_revoked_once_revoked() -> None:
    code = _device_code()

    _ = code.revoke()

    assert code.is_revoked() is True


def test_its_setters_answer_the_code_so_a_caller_can_chain_them() -> None:
    code = _device_code()

    assert code.set_user_approved(True).set_last_polled_at(_POLLED_AT) is code


def test_its_reading_holds_neither_the_user_code_nor_the_identifier_in_full() -> None:
    reading = repr(_device_code())

    assert "BCDFGHJK" not in reading
    assert reading == "DeviceCode(identifier='dc-ident...')"
