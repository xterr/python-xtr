"""A lone surrogate is told apart from text, a character outside the BMP included."""

from __future__ import annotations

import pytest

from xtr_mime._lone_surrogate import LONE_SURROGATE


@pytest.mark.parametrize("text", ["\udcb1", "a\ud800", "\udfff b"])
def test_a_surrogate_code_point_is_found(text: str) -> None:
    assert LONE_SURROGATE.search(text) is not None


@pytest.mark.parametrize("text", ["", "Žluťoučký kůň", "\U0001f600", "\ud7ff\ue000"])
def test_text_holds_no_lone_surrogate(text: str) -> None:
    assert LONE_SURROGATE.search(text) is None
