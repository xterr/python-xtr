"""A value error is worded by the application's validator, or by a fixed message per type."""

from __future__ import annotations

from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
    ip_address,
)
from typing import Annotated, cast

import pytest
from pydantic import AfterValidator, BeforeValidator, EmailStr, NameEmail, TypeAdapter
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import ErrorDetails, to_json

from xtr_serializer.normalizer._built_in_words import value_error_message

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"


def own_check(value: str) -> str:
    msg = f"the application's own words about {value}"
    raise ValueError(msg)


def detail_of(type_: object, data: object) -> ErrorDetails:
    # Each type here is a type form; typed as a class, as every pydantic's TypeAdapter takes.
    adapter = TypeAdapter(cast("type[object]", type_), config={"strict": True})
    with pytest.raises(PydanticValidationError) as raised:
        _ = adapter.validate_json(to_json(data))
    [detail] = raised.value.errors(include_url=False)
    return detail


@pytest.mark.parametrize(
    ("type_", "data", "message"),
    [
        (IPv4Address, f"10.0.0.{PLANTED_VALUE}", "Input is not a valid IPv4 address"),
        (IPv6Address, f"::{PLANTED_VALUE}", "Input is not a valid IPv6 address"),
        (IPv4Network, f"10.0.0.0/{PLANTED_VALUE}", "Input is not a valid IPv4 network"),
        (IPv4Network, "10.0.0.1/24", "Input is not a valid IPv4 network"),
        (IPv6Network, f"::/{PLANTED_VALUE}", "Input is not a valid IPv6 network"),
        (IPv4Interface, f"10.0.0.{PLANTED_VALUE}/24", "Input is not a valid IPv4 interface"),
        (IPv6Interface, f"::{PLANTED_VALUE}/64", "Input is not a valid IPv6 interface"),
        (EmailStr, f"user@[IPv6:{PLANTED_VALUE}]", "value is not a valid email address"),
        (NameEmail, f"user@{PLANTED_VALUE}@x.com", "value is not a valid email address"),
    ],
    ids=[
        "ipv4-address",
        "ipv6-address",
        "ipv4-network",
        "ipv4-network-host-bits",
        "ipv6-network",
        "ipv4-interface",
        "ipv6-interface",
        "email",
        "name-email",
    ],
)
def test_a_built_in_type_is_refused_in_fixed_words(type_: object, data: str, message: str) -> None:
    assert value_error_message(detail_of(type_, data)) == message


@pytest.mark.parametrize(
    "type_",
    [
        Annotated[str, AfterValidator(ip_address)],
        Annotated[int, BeforeValidator(int)],
    ],
    ids=["standard-library-function", "built-in-function"],
)
def test_a_value_error_no_application_code_raised_is_refused_in_fixed_words(
    type_: object,
) -> None:
    message = value_error_message(detail_of(type_, PLANTED_VALUE))

    assert message == "Value error, the input is not valid for its type"


def test_the_words_of_an_application_validator_are_passed_on() -> None:
    detail = detail_of(Annotated[str, AfterValidator(own_check)], "x")

    assert value_error_message(detail) == "Value error, the application's own words about x"


def test_a_value_error_with_no_context_is_passed_on() -> None:
    detail = ErrorDetails(type="value_error", loc=(), msg="Value error, as worded", input=1)

    assert value_error_message(detail) == "Value error, as worded"
