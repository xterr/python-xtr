from __future__ import annotations

import pytest

from xtr_logging.verbosity import Verbosity


def test_the_values_leave_room_between_them() -> None:
    assert (Verbosity.SILENT, Verbosity.QUIET, Verbosity.NORMAL) == (8, 16, 32)
    assert (Verbosity.VERBOSE, Verbosity.VERY_VERBOSE, Verbosity.DEBUG) == (64, 128, 256)


def test_no_verbose_flag_is_normal() -> None:
    assert Verbosity.from_count(0) is Verbosity.NORMAL


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, Verbosity.VERBOSE),
        (2, Verbosity.VERY_VERBOSE),
        (3, Verbosity.DEBUG),
        (9, Verbosity.DEBUG),
    ],
)
def test_more_verbose_flags_raise_the_verbosity(count: int, expected: Verbosity) -> None:
    assert Verbosity.from_count(count) is expected


def test_quiet_wins_over_any_verbose_count() -> None:
    assert Verbosity.from_count(3, quiet=True) is Verbosity.QUIET


def test_silent_wins_over_quiet() -> None:
    assert Verbosity.from_count(3, quiet=True, silent=True) is Verbosity.SILENT
