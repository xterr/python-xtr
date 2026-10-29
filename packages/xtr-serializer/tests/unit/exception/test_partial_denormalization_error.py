"""Every error found in data is listed in one message, and the data itself never is."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.round_trips import round_trips
from xtr_serializer.exception import (
    ExtraAttributesError,
    InvalidArgumentError,
    NotNormalizableValueError,
    PartialDenormalizationError,
    SerializerError,
    UnexpectedValueError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_it_is_an_unexpected_value() -> None:
    assert PartialDenormalizationError.__mro__ == (
        PartialDenormalizationError,
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_it_keeps_the_data_and_every_error_found_in_it() -> None:
    data = {"email": None, "age": "forty"}
    errors = (
        NotNormalizableValueError("Field required", path="email"),
        NotNormalizableValueError("Input should be a valid integer", path="age"),
    )

    error = PartialDenormalizationError(data, errors)

    assert error.data is data
    assert error.errors == errors


def test_it_refuses_an_empty_tuple_of_errors() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = PartialDenormalizationError({}, ())

    assert str(refused.value) == "PartialDenormalizationError needs at least one error to report"


def test_its_message_lists_every_error() -> None:
    error = PartialDenormalizationError(
        {},
        (
            NotNormalizableValueError(
                "Input should be a valid integer",
                path="age",
                expected_types=("int",),
                current_type="str",
            ),
            ExtraAttributesError(("nickname",), path="customer"),
        ),
    )

    assert str(error) == (
        "the data could not be denormalized (2 errors): "
        "at 'age': Input should be a valid integer (expected 'int', got 'str'); "
        "at 'customer': extra attributes are not allowed: 'nickname'"
    )


def test_its_message_counts_a_single_error_as_one() -> None:
    error = PartialDenormalizationError(
        {},
        (NotNormalizableValueError("Field required", path="email"),),
    )

    assert str(error) == "the data could not be denormalized (1 error): at 'email': Field required"


def test_it_never_renders_the_data(secret: str) -> None:
    error = PartialDenormalizationError(
        {"password": secret, "email": None},
        (NotNormalizableValueError("Field required", path="email"),),
    )

    assert secret not in str(error)
    assert secret not in repr(error)


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = PartialDenormalizationError(
        {"email": None, "age": "forty"},
        (
            NotNormalizableValueError("Field required", path="email"),
            NotNormalizableValueError(
                "Input should be a valid integer",
                path="age",
                expected_types=("int",),
                current_type="str",
            ),
        ),
    )

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is PartialDenormalizationError
        assert restored.args == (str(error),)
        assert str(restored) == str(error)
        assert restored.data == {"email": None, "age": "forty"}
        assert [str(found) for found in restored.errors] == [str(found) for found in error.errors]


def test_its_traceback_lists_the_errors_and_never_the_data(
    secret: str,
    traceback_of: Callable[[SerializerError], str],
) -> None:
    error = PartialDenormalizationError(
        {"password": secret, "email": None},
        (NotNormalizableValueError("Field required", path="email"),),
    )

    rendered = traceback_of(error)

    assert "at 'email': Field required" in rendered
    assert secret not in rendered
