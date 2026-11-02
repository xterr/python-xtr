"""A value that does not convert is described by where it is and which types, never by what."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import (
    NotNormalizableValueError,
    SerializerError,
    UnexpectedValueError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_it_is_an_unexpected_value() -> None:
    assert NotNormalizableValueError.__mro__ == (
        NotNormalizableValueError,
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_it_keeps_what_it_was_told() -> None:
    error = NotNormalizableValueError(
        "Input should be a valid number",
        path="items[0].price",
        expected_types=("int", "float"),
        current_type="str",
        error_type="float_parsing",
    )

    assert error.message == "Input should be a valid number"
    assert error.path == "items[0].price"
    assert error.expected_types == ("int", "float")
    assert error.current_type == "str"
    assert error.error_type == "float_parsing"


def test_it_knows_nothing_it_was_not_told() -> None:
    error = NotNormalizableValueError("Field required")

    assert error.path is None
    assert error.expected_types == ()
    assert error.current_type is None
    assert error.error_type is None


def test_a_message_alone_is_the_whole_message() -> None:
    assert str(NotNormalizableValueError("Field required")) == "Field required"


def test_its_message_starts_with_the_path() -> None:
    error = NotNormalizableValueError("Field required", path="customer.email")

    assert str(error) == "at 'customer.email': Field required"


def test_its_message_ends_with_the_types_expected_and_the_type_found() -> None:
    error = NotNormalizableValueError(
        "Input should be a valid number",
        path="items[0].price",
        expected_types=("int", "float"),
        current_type="str",
    )

    assert str(error) == (
        "at 'items[0].price': Input should be a valid number (expected 'int' | 'float', got 'str')"
    )


def test_its_message_names_the_types_expected_when_the_type_found_is_unknown() -> None:
    error = NotNormalizableValueError("Input should be a valid integer", expected_types=("int",))

    assert str(error) == "Input should be a valid integer (expected 'int')"


def test_its_message_names_the_type_found_when_no_type_is_expected() -> None:
    error = NotNormalizableValueError("Input has no JSON form", current_type="set")

    assert str(error) == "Input has no JSON form (got 'set')"


def test_its_message_leaves_the_error_type_to_programs() -> None:
    assert str(NotNormalizableValueError("Field required", error_type="missing")) == (
        "Field required"
    )


def test_a_path_cannot_break_its_message_across_lines() -> None:
    error = NotNormalizableValueError("Field required", path="tags.x\nINFO forged")

    assert str(error) == "at 'tags.x\\nINFO forged': Field required"


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = NotNormalizableValueError(
        "Input should be a valid number",
        path="items[0].price",
        expected_types=("int", "float"),
        current_type="str",
        error_type="float_parsing",
    )

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is NotNormalizableValueError
        assert restored.args == (str(error),)
        assert str(restored) == str(error)
        assert restored.message == "Input should be a valid number"
        assert restored.path == "items[0].price"
        assert restored.expected_types == ("int", "float")
        assert restored.current_type == "str"
        assert restored.error_type == "float_parsing"


def test_its_traceback_names_the_type_of_a_secret_and_never_the_secret(
    secret: str,
    traceback_of: Callable[[SerializerError], str],
) -> None:
    error = NotNormalizableValueError(
        "Input should be a valid integer",
        path="pin",
        expected_types=("int",),
        current_type=type(secret).__name__,
        error_type="int_parsing",
    )

    rendered = traceback_of(error)

    assert "at 'pin': Input should be a valid integer (expected 'int', got 'str')" in rendered
    assert secret not in rendered
