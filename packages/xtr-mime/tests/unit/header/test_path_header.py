from __future__ import annotations

import pytest

from xtr_mime import Address
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import PathHeader


def test_a_single_address_can_be_set_and_fetched() -> None:
    address = Address("chris@swiftmailer.org")

    assert PathHeader("Return-Path", address).get_address() is address


def test_the_address_must_comply_with_rfc_2822() -> None:
    with pytest.raises(RfcComplianceError):
        _ = PathHeader("Return-Path", Address("chr is@swiftmailer.org"))


def test_the_value_is_an_angle_addr_with_a_valid_address() -> None:
    header = PathHeader("Return-Path", Address("chris@swiftmailer.org"))

    assert header.get_body_as_string() == "<chris@swiftmailer.org>"


def test_the_address_is_idn_encoded() -> None:
    header = PathHeader("Return-Path", Address("chris@swïftmailer.org"))

    assert header.get_body_as_string() == "<chris@xn--swftmailer-78a.org>"


@pytest.mark.xfail(
    strict=True,
    raises=RfcComplianceError,
    reason="the engine has no raw UTF-8 form for an angle-bracketed path",
)
def test_the_address_must_be_encodable_with_utf8_characters_in_the_local_part() -> None:
    header = PathHeader("Return-Path", Address("chrïs@swiftmailer.org"))

    assert header.get_body_as_string() == "<chrïs@swiftmailer.org>"


def test_set_body() -> None:
    header = PathHeader("Return-Path", Address("foo@example.com"))
    address = Address("foo@bar.tld")

    header.set_body(address)

    assert header.get_address() is address


def test_set_body_refuses_what_is_not_an_address() -> None:
    header = PathHeader("Return-Path", Address("foo@example.com"))

    with pytest.raises(InvalidArgumentError):
        header.set_body("foo@bar.tld")


def test_get_body() -> None:
    address = Address("foo@bar.tld")

    assert PathHeader("Return-Path", address).get_body() is address


def test_set_address() -> None:
    header = PathHeader("Return-Path", Address("foo@example.com"))
    address = Address("foo@bar.tld")

    header.set_address(address)

    assert header.get_body() is address


def test_the_name_of_the_address_is_not_written() -> None:
    header = PathHeader("Return-Path", Address("some@path", "any ignored name"))

    assert header.get_body_as_string() == "<some@path>"


def test_to_string() -> None:
    header = PathHeader("Return-Path", Address("chris@swiftmailer.org"))

    assert header.to_string() == "Return-Path: <chris@swiftmailer.org>"
