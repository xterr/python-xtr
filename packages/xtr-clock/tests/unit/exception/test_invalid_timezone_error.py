from __future__ import annotations

from xtr_clock import ClockError, InvalidTimezoneError


def test_it_carries_the_name_that_could_not_be_resolved() -> None:
    assert InvalidTimezoneError("Nope/Nope").timezone == "Nope/Nope"


def test_it_names_the_offending_timezone_in_its_message() -> None:
    assert "'Nope/Nope'" in str(InvalidTimezoneError("Nope/Nope"))


def test_its_message_says_what_would_have_been_accepted() -> None:
    message = str(InvalidTimezoneError("Nope/Nope"))

    assert "Europe/Paris" in message
    assert "+02:00" in message


def test_it_is_a_clock_error() -> None:
    assert isinstance(InvalidTimezoneError("x"), ClockError)


def test_it_is_also_a_value_error() -> None:
    assert isinstance(InvalidTimezoneError("x"), ValueError)
