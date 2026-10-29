from __future__ import annotations

import pytest

from xtr_mime import Address
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import PathHeader


def test_a_single_address_can_be_set_and_fetched() -> None:
    address = Address("chris@example.org")

    assert PathHeader("Return-Path", address).get_address() is address


def test_the_address_must_comply_with_rfc_2822() -> None:
    with pytest.raises(RfcComplianceError):
        _ = PathHeader("Return-Path", Address("chr is@example.org"))


def test_the_value_is_an_angle_addr_with_a_valid_address() -> None:
    header = PathHeader("Return-Path", Address("chris@example.org"))

    assert header.get_body_as_string() == "<chris@example.org>"


def test_the_address_is_idn_encoded() -> None:
    header = PathHeader("Return-Path", Address("chris@swïftmailer.org"))

    assert header.get_body_as_string() == "<chris@xn--swftmailer-78a.org>"


def test_the_address_must_be_encodable_with_utf8_characters_in_the_local_part() -> None:
    header = PathHeader("Return-Path", Address("chrïs@example.org"))

    assert header.get_body_as_string() == "<chrïs@example.org>"


def test_a_utf8_local_part_keeps_the_domain_in_punycode() -> None:
    header = PathHeader("Return-Path", Address("chrïs@swïftmailer.org"))

    assert header.to_string() == "Return-Path: <chrïs@xn--swftmailer-78a.org>"


def test_a_comment_after_a_domain_literal_is_not_written() -> None:
    header = PathHeader("Return-Path", Address("chris@[192.0.2.1] (comment)"))

    assert header.get_body_as_string() == "<chris@[192.0.2.1]>"


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
    header = PathHeader("Return-Path", Address("chris@example.org"))

    assert header.to_string() == "Return-Path: <chris@example.org>"
