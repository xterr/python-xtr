from __future__ import annotations

import io

import pytest

from tests.support.records import make_record
from xtr_logging import Level
from xtr_logging.handler.console_handler import ConsoleHandler
from xtr_logging.verbosity import Verbosity


def test_the_default_verbosity_handles_warnings_and_up() -> None:
    handler = ConsoleHandler(io.StringIO())

    assert handler.level is Level.WARNING
    assert handler.is_handling(make_record(Level.WARNING))
    assert not handler.is_handling(make_record(Level.NOTICE))


def test_the_verbosity_property_reports_the_current_verbosity() -> None:
    handler = ConsoleHandler(io.StringIO(), Verbosity.VERBOSE)

    assert handler.verbosity is Verbosity.VERBOSE
    assert handler.level is Level.NOTICE


@pytest.mark.parametrize(
    ("verbosity", "expected"),
    [
        (Verbosity.QUIET, Level.ERROR),
        (Verbosity.NORMAL, Level.WARNING),
        (Verbosity.VERBOSE, Level.NOTICE),
        (Verbosity.VERY_VERBOSE, Level.INFO),
        (Verbosity.DEBUG, Level.DEBUG),
    ],
)
def test_each_verbosity_maps_to_its_level(verbosity: Verbosity, expected: Level) -> None:
    assert ConsoleHandler(io.StringIO(), verbosity).level is expected


def test_set_verbosity_moves_the_level() -> None:
    handler = ConsoleHandler(io.StringIO())

    handler.set_verbosity(Verbosity.DEBUG)

    assert handler.verbosity is Verbosity.DEBUG
    assert handler.level is Level.DEBUG


def test_a_partial_map_overrides_only_its_keys() -> None:
    handler = ConsoleHandler(io.StringIO(), verbosity_levels={Verbosity.NORMAL: Level.INFO})

    assert handler.level is Level.INFO
    handler.set_verbosity(Verbosity.QUIET)
    assert handler.level is Level.ERROR


def test_it_writes_the_line_to_the_given_stream() -> None:
    stream = io.StringIO()
    handler = ConsoleHandler(stream)

    _ = handler.handle(make_record(Level.ERROR, "boom", channel="ops"))

    assert "[ops] boom" in stream.getvalue()


def test_it_writes_to_stderr_when_no_stream_is_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = ConsoleHandler()

    _ = handler.handle(make_record(Level.ERROR, "boom"))

    assert "boom" in capsys.readouterr().err
