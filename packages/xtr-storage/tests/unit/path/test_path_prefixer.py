from __future__ import annotations

from xtr_storage.path.path_prefixer import PathPrefixer


def test_it_joins_a_prefix_to_a_path() -> None:
    assert PathPrefixer("a/b").prefix_path("c/d.txt") == "a/b/c/d.txt"


def test_it_trims_leading_separators_from_the_path_before_joining() -> None:
    prefixer = PathPrefixer("a")

    assert prefixer.prefix_path("/c.txt") == "a/c.txt"
    assert prefixer.prefix_path("\\c.txt") == "a/c.txt"


def test_an_empty_prefix_leaves_the_path_untouched() -> None:
    assert PathPrefixer("").prefix_path("c/d.txt") == "c/d.txt"


def test_a_bare_separator_prefix_stays_the_separator() -> None:
    assert PathPrefixer("/").prefix_path("c.txt") == "/c.txt"


def test_a_trailing_separator_in_the_prefix_is_collapsed() -> None:
    assert PathPrefixer("a/").prefix_path("c.txt") == "a/c.txt"


def test_it_strips_the_prefix_back_off_a_path() -> None:
    assert PathPrefixer("a/b").strip_prefix("a/b/c/d.txt") == "c/d.txt"


def test_stripping_an_empty_prefix_returns_the_path_unchanged() -> None:
    assert PathPrefixer("").strip_prefix("c/d.txt") == "c/d.txt"


def test_it_prefixes_a_directory_path_with_a_trailing_separator() -> None:
    assert PathPrefixer("a").prefix_directory_path("sub") == "a/sub/"


def test_it_does_not_double_the_separator_on_a_directory_path() -> None:
    assert PathPrefixer("a").prefix_directory_path("sub/") == "a/sub/"


def test_an_empty_directory_path_under_an_empty_prefix_stays_empty() -> None:
    assert PathPrefixer("").prefix_directory_path("") == ""


def test_an_empty_directory_path_under_a_prefix_yields_the_prefix() -> None:
    assert PathPrefixer("a").prefix_directory_path("") == "a/"
