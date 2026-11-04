"""The names an HTML body refers to through ``cid:``, found in one pass over it."""

from __future__ import annotations

import time

import pytest

from xtr_mime._html_references import referenced_names


@pytest.mark.parametrize(
    ("html", "names"),
    [
        ('<img src="cid:a.gif">', ["a.gif"]),
        ("<img src='cid:a.gif'>", ["a.gif"]),
        ("<IMG SRC=cid:a.gif>", ["a.gif"]),
        ("<img\nalt=x\nsrc = cid:a.gif>", ["a.gif"]),
        ('<div background="cid:a.gif"></div>', ["a.gif"]),
        ("<td class=x background=cid:a.gif>", ["a.gif"]),
    ],
    ids=["double-quoted", "single-quoted", "bare", "spaced", "background", "bare-background"],
)
def test_a_reference_is_found(html: str, names: list[str]) -> None:
    assert referenced_names(html) == names


@pytest.mark.parametrize(
    "html",
    [
        '<img src="a.gif">',
        '<img src="cid:a.gif',
        '<img src="cid:a.gif\n">',
        "<img>src=cid:a.gif",
        '<image src="cid:a.gif">',
        '<p>src="cid:a.gif"</p>',
        '<img src="cid:">',
    ],
    ids=["no-cid", "unclosed", "line-break", "outside", "other-tag", "no-tag", "empty"],
)
def test_no_reference_is_found(html: str) -> None:
    assert referenced_names(html) == []


def test_the_last_source_of_a_tag_is_the_one_read() -> None:
    assert referenced_names('<img src="cid:a.gif" src="cid:b.gif">') == ["b.gif"]


def test_a_quoted_name_runs_to_its_closing_quote_past_the_end_of_the_tag() -> None:
    assert referenced_names('<img src="cid:a>b.gif">') == ["a>b.gif"]


def test_a_bare_name_ends_at_a_space_or_the_end_of_the_tag() -> None:
    assert referenced_names("<img src=cid:a.gif alt=x> <img src=cid:b.gif>") == ["a.gif", "b.gif"]


def test_the_search_goes_on_after_a_reference() -> None:
    html = '<img src="cid:a.gif"> <img src="cid:b.gif">'

    assert referenced_names(html) == ["a.gif", "b.gif"]


def test_a_tag_left_open_is_searched_up_to_the_next_end_of_a_tag() -> None:
    # The first tag runs to the only ">": its last source is the one read, the other is not.
    assert referenced_names('<img src="cid:a.gif" <img src="cid:b.gif">') == ["b.gif"]


def test_a_tag_opened_after_the_last_reference_before_the_end_of_a_tag_has_none() -> None:
    assert referenced_names("<img src=cid:a.gif <img src=b.gif>") == ["a.gif"]


def test_quoted_names_come_before_bare_ones_and_sources_before_backgrounds() -> None:
    html = '<p background="cid:d"> <img src=cid:b> <img src="cid:a"> <p background=cid:c>'

    assert referenced_names(html) == ["a", "b", "d", "c"]


def test_a_name_is_returned_once() -> None:
    html = '<img src="cid:a.gif"> <img src=cid:a.gif> <div background="cid:a.gif">'

    assert referenced_names(html) == ["a.gif"]


@pytest.mark.parametrize(
    "run", ["<a ", "<img src=", 'src="cid:', "<img src=cid:", "<a background=cid:", "<img src='"]
)
def test_a_megabyte_of_tags_left_open_is_searched_in_linear_time(run: str) -> None:
    html = run * (1_000_000 // len(run))
    started = time.perf_counter()

    _ = referenced_names(html)

    assert time.perf_counter() - started < 1
