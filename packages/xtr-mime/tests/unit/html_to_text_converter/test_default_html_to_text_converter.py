"""The default HTML-to-text converter: the text of an HTML body, without its markup."""

from __future__ import annotations

import pytest

from xtr_mime.html_to_text_converter import DefaultHtmlToTextConverter
from xtr_mime.html_to_text_converter.default_html_to_text_converter import _TextCollector


def _convert(html: str) -> str:
    return DefaultHtmlToTextConverter().convert(html, "utf-8")


def test_the_head_and_the_styles_are_dropped_and_the_tags_stripped() -> None:
    converter = DefaultHtmlToTextConverter()

    text = converter.convert(
        '<head><meta charset="utf-8"></head><b>HTML</b><style>css</style>', "UTF-8"
    )

    assert text == "HTML"


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ("<p>Hello <b>world</b></p>", "Hello world"),
        ('<STYLE type="text/css">a { color: red }</STYLE>x', "x"),
        ("<script>if (a < b) { alert('</p>') }</script>x", "x"),
        ("<html><head><title>T</title><style>s</style></head><body>B</body></html>", "B"),
        ("<head><head>inner</head>outer</head>", "outer"),
        ("<header>Top</header>", "Top"),
        ("<stylesheet>kept</stylesheet>", "kept"),
    ],
    ids=[
        "tags",
        "style with attributes, in capitals",
        "script",
        "head holding a title and a style",
        "head closed at its first end tag",
        "header is not head",
        "stylesheet is not style",
    ],
)
def test_markup_is_stripped_and_hidden_elements_dropped(html: str, text: str) -> None:
    assert _convert(html) == text


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ("<head>title", "title"),
        ("<style>css", "css"),
        ("a<head>b</style>c", "abc"),
    ],
)
def test_an_element_never_closed_hides_nothing(html: str, text: str) -> None:
    assert _convert(html) == text


def test_entities_are_decoded() -> None:
    assert _convert("Fish &amp; chips &lt;3 &#x41;&#66; &eacute;") == "Fish & chips <3 AB é"


def test_a_reference_padded_with_more_zeros_than_int_reads_names_its_character() -> None:
    assert _convert("<p>Hi &#" + "0" * 4300 + "65;</p>") == "Hi A"


@pytest.mark.parametrize(
    ("reference", "character"),
    [
        ("&#x" + "0" * 4300 + "41;", "A"),
        ("&#" + "0" * 4300 + "65", "A"),
        ("&#" + "0" * 4300 + "1048576;", "\U00100000"),
        ("&#X" + "0" * 4300 + "100000;", "\U00100000"),
        ("&#" + "0" * 4300 + ";", "\ufffd"),
    ],
    ids=[
        "hexadecimal",
        "without a semicolon",
        "seven decimal digits",
        "six hexadecimal digits",
        "zero",
    ],
)
def test_leading_zeros_do_not_change_the_character_a_reference_names(
    reference: str, character: str
) -> None:
    assert _convert(f"a {reference} b") == f"a {character} b"


@pytest.mark.parametrize(
    "reference",
    [
        "&#" + "1" * 5000 + ";",
        "&#x" + "f" * 5000 + ";",
        "&#" + "9" * 5000,
        "&#" + "0" * 4300 + "11141120;",
        "&#x" + "0" * 4300 + "1000000;",
    ],
    ids=[
        "decimal",
        "hexadecimal",
        "without a semicolon",
        "eight decimal digits after zeros",
        "seven hexadecimal digits after zeros",
    ],
)
def test_a_reference_past_the_last_code_point_reads_as_the_replacement_character(
    reference: str,
) -> None:
    assert _convert(f"a {reference} b") == "a \ufffd b"


@pytest.mark.parametrize(
    ("html", "text"),
    [
        ('<a title="&#' + "1" * 5000 + ';">x</a>', "x"),
        ("<title>&#" + "0" * 4300 + "65;</title>", "A"),
        ("<textarea>&#" + "1" * 5000 + ";</textarea>", "\ufffd"),
    ],
    ids=["attribute value", "title", "textarea"],
)
def test_a_long_reference_converts_wherever_the_parser_decodes_one(html: str, text: str) -> None:
    assert _convert(html) == text


def test_comments_and_declarations_are_dropped() -> None:
    assert _convert("<!DOCTYPE html>a<!-- hidden -->b<?xml x?>c<![CDATA[d]]>e") == "abce"


def test_a_less_than_sign_that_opens_no_tag_is_kept() -> None:
    assert _convert("a < b") == "a < b"


def test_whitespace_collapses_within_lines_and_blank_lines_to_one() -> None:
    html = "<p>\n  Hello\t\t world  \r\n</p>\r\n\n\n\n<p>Bye&nbsp;&nbsp;now</p>\n"

    assert _convert(html) == "Hello world\n\nBye now"


def test_the_charset_does_not_change_the_text() -> None:
    converter = DefaultHtmlToTextConverter()

    assert converter.convert("<b>caf&eacute;</b>", "iso-8859-1") == "café"


@pytest.mark.parametrize(
    "html",
    [
        "<![foo[bar]]>",
        "<![if x]>",
        "<!x",
        "<a href='",
        "</",
        "<a b='\ud800'>",
        "&#xD800;&#0;&#x110000;",
        "\ud800<b>\udfff</b>",
        "<" * 100,
    ],
)
def test_malformed_markup_converts_without_an_error(html: str) -> None:
    assert isinstance(_convert(html), str)


def test_a_lone_surrogate_is_kept_and_a_surrogate_reference_replaced() -> None:
    assert _convert("\ud800<b>x</b>&#xD800;") == "\ud800x\ufffd"


def test_a_marked_section_with_an_unknown_keyword_is_read_to_its_end() -> None:
    collector = _TextCollector()
    collector.rawdata = "<![foo[bar]]>after"

    assert collector.parse_marked_section(0) == len("<![foo[bar]]>")


def test_a_marked_section_with_an_unknown_keyword_and_no_end_runs_to_the_end() -> None:
    collector = _TextCollector()
    collector.rawdata = "<![foo[bar"

    assert collector.parse_marked_section(0) == len("<![foo[bar")


def test_a_marked_section_with_a_known_keyword_is_read_by_the_parser() -> None:
    collector = _TextCollector()
    collector.rawdata = "<![if x]>after"

    assert collector.parse_marked_section(0) == len("<![if x]>")
