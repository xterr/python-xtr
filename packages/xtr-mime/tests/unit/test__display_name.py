"""A display name loses its control characters and its padding; a lone surrogate is refused."""

from __future__ import annotations

import pytest

from xtr_mime._display_name import clean_display_name
from xtr_mime.exception import RfcComplianceError


def test_control_characters_are_dropped_but_a_tab_is_kept() -> None:
    assert clean_display_name("a\x00b\r\nc\td\x7f", "The name") == "abc\td"


def test_the_name_is_trimmed() -> None:
    assert clean_display_name(" \t\x0bName\0 ", "The name") == "Name"


@pytest.mark.parametrize("name", ["\udcb1", "a\ud800", "\udfff b"])
def test_a_name_holding_a_lone_surrogate_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match=r"^The group name .* lone surrogate"):
        _ = clean_display_name(name, "The group name")


@pytest.mark.parametrize("name", ["", "Žluťoučký kůň", "\U0001f600", "\ud7ff\ue000"])
def test_a_name_of_text_is_kept(name: str) -> None:
    assert clean_display_name(name, "The name") == name
