"""Attributes a type does not declare are named in the error; what they held is not."""

from __future__ import annotations

from xtr_serializer.exception import (
    ExtraAttributesError,
    NotNormalizableValueError,
    SerializerError,
    UnexpectedValueError,
)


def test_it_is_a_value_that_cannot_be_denormalized() -> None:
    assert ExtraAttributesError.__mro__ == (
        ExtraAttributesError,
        NotNormalizableValueError,
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_it_keeps_the_attributes_and_where_the_data_had_them() -> None:
    error = ExtraAttributesError(
        ("nickname", "age"),
        path="customer",
        expected_types=("Customer",),
        current_type="dict",
        error_type="extra_forbidden",
    )

    assert error.extra_attributes == ("nickname", "age")
    assert error.path == "customer"
    assert error.expected_types == ("Customer",)
    assert error.current_type == "dict"
    assert error.error_type == "extra_forbidden"


def test_it_knows_nothing_it_was_not_told() -> None:
    error = ExtraAttributesError(("nickname",))

    assert error.path is None
    assert error.expected_types == ()
    assert error.current_type is None
    assert error.error_type is None


def test_its_message_names_every_extra_attribute() -> None:
    assert str(ExtraAttributesError(("nickname", "age"))) == (
        "extra attributes are not allowed: 'nickname', 'age'"
    )


def test_its_message_says_where_the_data_had_them() -> None:
    assert str(ExtraAttributesError(("nickname",), path="customer")) == (
        "at 'customer': extra attributes are not allowed: 'nickname'"
    )


def test_an_attribute_name_cannot_break_its_message_across_lines() -> None:
    assert str(ExtraAttributesError(("nick\nINFO forged",))) == (
        "extra attributes are not allowed: 'nick\\nINFO forged'"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = ExtraAttributesError(("password_confirmation",), path="account")
    error.__cause__ = ValueError(f"[type=extra_forbidden, input_value={secret!r}]")

    assert secret not in str(error)
    assert secret not in repr(error)
