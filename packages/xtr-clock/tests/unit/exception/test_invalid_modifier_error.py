from __future__ import annotations

from xtr_clock import ClockError, InvalidModifierError


def test_it_carries_the_modifier_that_could_not_be_read() -> None:
    assert InvalidModifierError("+1 dya", "unknown unit").modifier == "+1 dya"


def test_it_carries_the_reason_it_could_not_be_read() -> None:
    assert InvalidModifierError("+1 dya", "unknown unit").reason == "unknown unit"


def test_it_names_both_the_modifier_and_the_reason_in_its_message() -> None:
    message = str(InvalidModifierError("+1 dya", "unknown unit"))

    assert "'+1 dya'" in message
    assert "unknown unit" in message


def test_it_is_a_clock_error() -> None:
    assert isinstance(InvalidModifierError("x", "y"), ClockError)


def test_it_is_also_a_value_error() -> None:
    assert isinstance(InvalidModifierError("x", "y"), ValueError)
