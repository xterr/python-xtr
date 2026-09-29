from __future__ import annotations

import pytest

from xtr_storage.exception import InvalidVisibilityError
from xtr_storage.visibility import Visibility


def test_a_member_is_its_own_string() -> None:
    assert Visibility.PUBLIC == "public"
    assert Visibility.PRIVATE == "private"


def test_a_member_reads_as_its_string_when_formatted() -> None:
    assert f"{Visibility.PRIVATE}" == "private"


def test_parse_returns_a_member_unchanged() -> None:
    assert Visibility.parse(Visibility.PUBLIC) is Visibility.PUBLIC


def test_parse_reads_the_string_form() -> None:
    assert Visibility.parse("private") is Visibility.PRIVATE


def test_parse_refuses_a_word_no_member_carries() -> None:
    with pytest.raises(InvalidVisibilityError):
        _ = Visibility.parse("world")


def test_parse_names_the_word_it_refused() -> None:
    with pytest.raises(InvalidVisibilityError) as refused:
        _ = Visibility.parse("world")

    assert "world" in str(refused.value)


def test_a_refused_visibility_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="world"):
        _ = Visibility.parse("world")


def test_parse_is_case_sensitive() -> None:
    with pytest.raises(InvalidVisibilityError):
        _ = Visibility.parse("PUBLIC")
