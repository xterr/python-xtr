"""Attributes a type does not declare are named in the error; what they held is not."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.round_trips import round_trips
from xtr_serializer.exception import (
    ExtraAttributesError,
    InvalidArgumentError,
    NotNormalizableValueError,
    SerializerError,
    UnexpectedValueError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_refuses_an_empty_tuple_of_attributes() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = ExtraAttributesError(())

    assert str(refused.value) == "ExtraAttributesError needs at least one extra attribute"


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = ExtraAttributesError(
        ("nickname", "age"),
        path="customer",
        expected_types=("Customer",),
        current_type="dict",
        error_type="extra_forbidden",
    )

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is ExtraAttributesError
        assert restored.args == (str(error),)
        assert str(restored) == str(error)
        assert str(restored).endswith("(expected 'Customer', got 'dict')")
        assert restored.extra_attributes == ("nickname", "age")
        assert restored.path == "customer"
        assert restored.expected_types == ("Customer",)
        assert restored.current_type == "dict"
        assert restored.error_type == "extra_forbidden"


def test_its_traceback_names_the_attributes_and_never_their_values(
    secret: str,
    traceback_of: Callable[[SerializerError], str],
) -> None:
    error = ExtraAttributesError(
        ("password_confirmation",),
        path="account",
        current_type=type(secret).__name__,
    )

    rendered = traceback_of(error)

    assert "at 'account': extra attributes are not allowed: 'password_confirmation'" in rendered
    assert secret not in rendered
