from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from xtr_web_profiler.templating import create_environment, format_bytes, format_ms, format_time


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "n/a"),
        (512, "512 B"),
        (1536, "1.5 KiB"),
        (3 * 1024**3, "3.0 GiB"),
        (2 * 1024**5, "2048.0 TiB"),
    ],
)
def test_sizes_are_shown_in_the_largest_unit_they_fill(value: int | None, expected: str) -> None:
    assert format_bytes(value) == expected


def test_durations_and_times_are_shown_readably() -> None:
    assert format_ms(12.345) == "12.3 ms"
    assert format_ms(None) == "n/a"
    assert format_time(1_767_225_600) == "2026-01-01 00:00:00"
    assert format_time(None) == "n/a"


def test_a_file_link_follows_the_configured_format() -> None:
    linked = create_environment("vscode://file/{file}:{line}")
    unlinked = create_environment()

    assert linked.from_string("{{ 'a.py' | file_link(3) }}").render() == "vscode://file/a.py:3"
    assert unlinked.from_string("{{ 'a.py' | file_link(3) }}").render() == "None"


def test_values_are_escaped_and_an_undefined_name_fails() -> None:
    environment = create_environment()

    assert environment.from_string("{{ value }}").render(value="<b>") == "&lt;b&gt;"
    with pytest.raises(UndefinedError):
        _ = environment.from_string("{{ missing }}").render()
