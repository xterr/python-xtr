from __future__ import annotations

import pytest

from xtr_storage.exception import CorruptedPathDetectedError, PathTraversalDetectedError
from xtr_storage.path.whitespace_path_normalizer import WhitespacePathNormalizer


@pytest.fixture
def normalizer() -> WhitespacePathNormalizer:
    return WhitespacePathNormalizer()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("a/b/c", "a/b/c"),
        ("\\a\\b\\c", "a/b/c"),
        ("a/./b", "a/b"),
        ("./a", "a"),
        ("a//b", "a/b"),
        ("/a/b/", "a/b"),
        ("a/../b", "b"),
        ("a/..", ""),
        ("\\a/./b//c/../d", "a/b/d"),
        ("", ""),
        (".", ""),
    ],
)
def test_it_reduces_a_path_to_its_plain_form(
    normalizer: WhitespacePathNormalizer,
    path: str,
    expected: str,
) -> None:
    assert normalizer.normalize_path(path) == expected


@pytest.mark.parametrize("path", ["../x", "..", "a/../../b"])
def test_it_refuses_a_path_that_climbs_above_the_root(
    normalizer: WhitespacePathNormalizer,
    path: str,
) -> None:
    with pytest.raises(PathTraversalDetectedError):
        _ = normalizer.normalize_path(path)


def test_it_names_the_offending_path_on_a_traversal(
    normalizer: WhitespacePathNormalizer,
) -> None:
    with pytest.raises(PathTraversalDetectedError) as caught:
        _ = normalizer.normalize_path("../etc")

    assert caught.value.path == "../etc"


def test_it_refuses_any_parent_segment_when_traversal_is_disallowed() -> None:
    normalizer = WhitespacePathNormalizer(allow_relative_path_traversal=False)

    with pytest.raises(PathTraversalDetectedError):
        _ = normalizer.normalize_path("a/../b")


def test_it_still_resolves_a_parent_segment_when_traversal_is_allowed() -> None:
    normalizer = WhitespacePathNormalizer(allow_relative_path_traversal=True)

    assert normalizer.normalize_path("a/../b") == "b"


@pytest.mark.parametrize("path", ["a/\x00b", "a/\u200bb", "\tfile", "a\rb"])
def test_it_refuses_a_control_or_formatting_character(
    normalizer: WhitespacePathNormalizer,
    path: str,
) -> None:
    with pytest.raises(CorruptedPathDetectedError):
        _ = normalizer.normalize_path(path)


def test_it_names_the_offending_path_on_a_corrupt_character(
    normalizer: WhitespacePathNormalizer,
) -> None:
    with pytest.raises(CorruptedPathDetectedError) as caught:
        _ = normalizer.normalize_path("a/\x00b")

    assert caught.value.path == "a/\x00b"
