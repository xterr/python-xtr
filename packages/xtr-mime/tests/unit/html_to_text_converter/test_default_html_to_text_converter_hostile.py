"""Hostile HTML converts in time that grows with its length, never with its square.

An HTML body may come from anyone, so markup built to make a parser backtrack — deep
nesting, tags never closed, endless attributes — must cost no more per byte than text. Each
case converts inputs of growing sizes, and the CPU time each takes is held to linear growth
(see :mod:`tests.support.growth`), so a machine slowed by other work does not decide.

Megabytes of character reference digits are held to a budget per megabyte instead, under the
interpreter's default limit on the digits ``int()`` reads and with no limit, as an application
may set it: reading such digits as a number would refuse them, or take time growing faster than
their count. The budget is in CPU time too, for the same reason.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Final

import pytest

from tests.support.growth import assert_linear_growth
from xtr_mime.html_to_text_converter import DefaultHtmlToTextConverter

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

_LARGEST: Final = 400_000
_MEGABYTE: Final = 1_000_000
_MEGABYTES: Final = 5
_SECONDS_PER_MEGABYTE: Final = 1.0

HOSTILE: Final[dict[str, Callable[[int], str]]] = {
    "deep nesting": lambda size: "<div>" * (size // 5),
    "unclosed tags": lambda size: "<a " * (size // 3),
    "less-than runs": lambda size: "<" * size,
    "attribute run": lambda size: "<a " + "b " * (size // 2) + ">",
    "unclosed quoted attribute": lambda size: '<a href="' + "x" * size,
    "ampersand runs": lambda size: "&#" * (size // 2),
    "unclosed comment": lambda size: "<!--" + "x" * size,
    "marked section runs": lambda size: "<![x[" * (size // 5),
    "unclosed head": lambda size: "<head>" + "<p>x</p>" * (size // 8),
    "unclosed style": lambda size: "<style>" + "</sty" * (size // 5),
    "whitespace runs": lambda size: " \t\n" * (size // 3),
}

LONG_REFERENCES: Final[dict[str, Callable[[int], str]]] = {
    "decimal": lambda size: "&#" + "1" * size,
    "zero-padded decimal": lambda size: "&#" + "0" * size + "65;",
    "hexadecimal": lambda size: "&#x" + "f" * size,
    "decimal references": lambda size: ("&#" + "9" * 8 + ";") * (size // 11),
    "hexadecimal references": lambda size: ("&#x" + "f" * 7 + ";") * (size // 11),
}


def _seconds(html: str) -> float:
    converter = DefaultHtmlToTextConverter()
    started = time.thread_time()
    _ = converter.convert(html, "utf-8")
    return time.thread_time() - started


@contextmanager
def _int_digit_limit(limit: int) -> Generator[None]:
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(limit)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(previous)


@pytest.mark.parametrize("build", HOSTILE.values(), ids=HOSTILE.keys())
def test_hostile_markup_converts_in_linear_time(build: Callable[[int], str]) -> None:
    converter = DefaultHtmlToTextConverter()

    _ = assert_linear_growth(lambda size: converter.convert(build(size), "utf-8"), _LARGEST // 4)


@pytest.mark.parametrize(
    "int_digit_limit",
    [sys.int_info.default_max_str_digits, 0],
    ids=["default int digit limit", "no int digit limit"],
)
@pytest.mark.parametrize("build", LONG_REFERENCES.values(), ids=LONG_REFERENCES.keys())
def test_megabytes_of_reference_digits_convert_in_under_a_second_per_megabyte(
    build: Callable[[int], str], int_digit_limit: int
) -> None:
    html = build(_MEGABYTES * _MEGABYTE)

    with _int_digit_limit(int_digit_limit):
        seconds = _seconds(html)

    assert seconds < _MEGABYTES * _SECONDS_PER_MEGABYTE
