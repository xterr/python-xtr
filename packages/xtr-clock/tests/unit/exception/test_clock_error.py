from __future__ import annotations

import pytest

from xtr_clock import ClockError, InvalidModifierError, InvalidTimezoneError


@pytest.mark.parametrize("error", [InvalidModifierError, InvalidTimezoneError])
def test_every_error_this_library_raises_derives_from_it(error: type[Exception]) -> None:
    assert issubclass(error, ClockError)


def test_it_is_an_exception() -> None:
    assert issubclass(ClockError, Exception)


def test_one_except_catches_anything_a_clock_can_go_wrong_with() -> None:
    with pytest.raises(ClockError):
        raise InvalidTimezoneError("Nope/Nope")
