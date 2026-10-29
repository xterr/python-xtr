"""Round trips rebuild an error every way one is copied, and fail for one that cannot be rebuilt."""

from __future__ import annotations

import pytest

from tests.support.round_trips import round_trips


class _KeywordOnlyError(Exception):
    """An error its arguments cannot rebuild: pickle and copy pass them by position."""

    def __init__(self, *, reason: str) -> None:
        super().__init__(f"refused: {reason}")


def test_it_rebuilds_the_error_four_times_as_new_errors_of_its_type() -> None:
    error = ValueError("the value is wrong")

    rebuilt = round_trips(error)

    assert [(type(one), one.args, one is error) for one in rebuilt] == [
        (ValueError, ("the value is wrong",), False),
    ] * 4


def test_it_fails_for_an_error_that_cannot_be_rebuilt() -> None:
    with pytest.raises(TypeError):
        _ = round_trips(_KeywordOnlyError(reason="a keyword"))
