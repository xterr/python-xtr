"""Hostile HTML converts in time that grows with its length, never with its square.

An HTML body may come from anyone, so markup built to make a parser backtrack — deep
nesting, tags never closed, endless attributes — must cost no more per byte than text. Each
case converts a small and a four times larger input; a quadratic cost would take sixteen times
as long, a linear one four.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final

import pytest

from xtr_mime.html_to_text_converter import DefaultHtmlToTextConverter

if TYPE_CHECKING:
    from collections.abc import Callable

_SMALL: Final = 100_000
_LARGE: Final = 4 * _SMALL
_GROWTH_LIMIT: Final = 10.0

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


def _seconds(html: str) -> float:
    converter = DefaultHtmlToTextConverter()
    started = time.perf_counter()
    _ = converter.convert(html, "utf-8")
    return time.perf_counter() - started


@pytest.mark.parametrize("build", HOSTILE.values(), ids=HOSTILE.keys())
def test_hostile_markup_converts_in_linear_time(build: Callable[[int], str]) -> None:
    small = min(_seconds(build(_SMALL)) for _ in range(3))
    large = min(_seconds(build(_LARGE)) for _ in range(3))

    assert large < max(small, 0.001) * _GROWTH_LIMIT
