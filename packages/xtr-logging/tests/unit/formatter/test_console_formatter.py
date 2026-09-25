from __future__ import annotations

from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging.formatter.console_formatter import ConsoleFormatter


def test_the_default_line_is_short_and_bracketed() -> None:
    record = make_record(Level.WARNING, "low disk", channel="ops")

    assert ConsoleFormatter().format(record) == "12:30:45 WARNING [ops] low disk\n"


def test_empty_context_and_extra_are_left_off_by_default() -> None:
    assert ConsoleFormatter().format(make_record(message="hi")).endswith("[app] hi\n")


def test_colours_are_off_by_default() -> None:
    rendered = ConsoleFormatter().format(make_record(Level.ERROR, "boom"))

    assert "\033[" not in rendered
    assert "ERROR" in rendered


def test_colours_wrap_the_level_name_when_on() -> None:
    rendered = ConsoleFormatter(colors=True).format(make_record(Level.ERROR, "boom"))

    assert "\033[31mERROR\033[0m" in rendered


def test_the_colour_is_graded_by_severity() -> None:
    formatter = ConsoleFormatter(colors=True)

    debug = formatter.format(make_record(Level.DEBUG, "trace"))
    emergency = formatter.format(make_record(Level.EMERGENCY, "down"))

    assert "\033[2mDEBUG\033[0m" in debug
    assert "\033[1;31mEMERGENCY\033[0m" in emergency


def test_only_the_level_token_is_wrapped_not_a_matching_word() -> None:
    rendered = ConsoleFormatter(colors=True).format(make_record(Level.ERROR, "ERROR happened"))

    assert rendered.count("\033[31m") == 1
    assert rendered.endswith("[app] ERROR happened\n")


def test_a_template_without_the_level_token_is_left_uncoloured() -> None:
    rendered = ConsoleFormatter("%message%\n", colors=True).format(make_record(Level.ERROR, "boom"))

    assert rendered == "boom\n"
