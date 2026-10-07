from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_recipes.exception import UnsafePathError
from xtr_recipes.safe_path import has_traversal, within

if TYPE_CHECKING:
    from pathlib import Path


def test_a_relative_path_inside_the_root_has_no_traversal() -> None:
    assert not has_traversal("src/app/config.py")


def test_an_absolute_path_is_traversal() -> None:
    assert has_traversal("/etc/passwd")


def test_a_path_climbing_out_is_traversal() -> None:
    assert has_traversal("../../outside.txt")


def test_a_dotdot_that_stays_inside_is_not_traversal() -> None:
    assert not has_traversal("a/../b")


def test_a_path_separated_with_backslashes_is_traversal() -> None:
    assert has_traversal("..\\..\\x")


def test_a_single_backslash_segment_is_traversal() -> None:
    assert has_traversal("config\\messenger.py")


def test_within_returns_the_resolved_path(tmp_path: Path) -> None:
    assert within(tmp_path, "src/app/config.py") == (tmp_path / "src/app/config.py").resolve()


def test_within_refuses_a_path_outside_the_project(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        _ = within(tmp_path, "../x")
