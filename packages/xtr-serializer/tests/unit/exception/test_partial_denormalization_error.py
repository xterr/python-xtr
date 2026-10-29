"""Every error found in data is listed in one message, and the data itself never is."""

from __future__ import annotations

from xtr_serializer.exception import (
    ExtraAttributesError,
    NotNormalizableValueError,
    PartialDenormalizationError,
    SerializerError,
    UnexpectedValueError,
)


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
        "at 'age': Input should be a valid integer (expected int, got str); "
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


def test_it_never_renders_what_its_errors_were_raised_from(secret: str) -> None:
    found = NotNormalizableValueError("Input should be a valid integer", path="pin")
    found.__cause__ = ValueError(f"[type=int_parsing, input_value={secret!r}]")
    error = PartialDenormalizationError({"pin": secret}, (found,))
    error.__cause__ = found

    assert secret not in str(error)
    assert secret not in repr(error)
