from __future__ import annotations

import pytest

from xtr_logging import InvalidLevelError, Level


def test_levels_carry_spaced_values() -> None:
    assert [level.value for level in Level] == [100, 200, 250, 300, 400, 500, 550, 600]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (Level.ERROR, Level.ERROR),
        (400, Level.ERROR),
        (3, Level.ERROR),
        (0, Level.EMERGENCY),
        (7, Level.DEBUG),
        ("error", Level.ERROR),
        ("ERROR", Level.ERROR),
        ("Notice", Level.NOTICE),
    ],
)
def test_parse_reads_every_accepted_spelling(given: Level | int | str, expected: Level) -> None:
    assert Level.parse(given) is expected


@pytest.mark.parametrize("given", [8, 99, 401, -1, "warn", "", True])
def test_parse_refuses_what_names_no_level(given: int | str) -> None:
    with pytest.raises(InvalidLevelError) as raised:
        _ = Level.parse(given)

    assert raised.value.value == given


def test_an_invalid_level_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="'loud' is not a log level"):
        _ = Level.parse("loud")


def test_lower_name_is_the_lower_case_name() -> None:
    assert Level.EMERGENCY.lower_name == "emergency"


@pytest.mark.parametrize(
    ("level", "severity"),
    [(Level.EMERGENCY, 0), (Level.ALERT, 1), (Level.NOTICE, 5), (Level.DEBUG, 7)],
)
def test_rfc5424_severity_runs_backwards_from_the_value(level: Level, severity: int) -> None:
    assert level.rfc5424 == severity


def test_a_threshold_includes_levels_at_or_above_it() -> None:
    assert Level.WARNING.includes(Level.WARNING)
    assert Level.WARNING.includes(Level.ERROR)
    assert not Level.WARNING.includes(Level.NOTICE)


def test_comparisons_are_strict() -> None:
    assert Level.ERROR.is_higher_than(Level.WARNING)
    assert not Level.ERROR.is_higher_than(Level.ERROR)
    assert Level.INFO.is_lower_than(Level.NOTICE)
