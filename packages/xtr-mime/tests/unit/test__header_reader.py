"""The reader the engine checks its own output with, the way an RFC 2047 mail client reads it."""

from __future__ import annotations

import pytest

from xtr_mime._header_reader import ReadGroup, read_address_list, read_unstructured


@pytest.mark.parametrize(
    ("body", "text"),
    [
        ("plain text", "plain text"),
        ("", ""),
        ("  padded  ", "padded"),
        ("a\tb", "a\tb"),
        ("=?utf-8?q?h=C3=A9llo?=", "héllo"),
        ("=?UTF-8?Q?a_b?=", "a b"),
        ("=?utf-8?b?aMOpbGxv?=", "héllo"),
        ("=?utf-8*en?q?x?=", "x"),
        # Whitespace between two encoded words is not text; elsewhere it is.
        ("=?utf-8?q?a?= =?utf-8?q?b?=", "ab"),
        ("=?utf-8?q?a?=\r\n =?utf-8?q?_b?=", "a b"),
        ("x =?utf-8?q?a?= y", "x a y"),
        # A character split between two encoded words is joined before it is decoded.
        ("=?utf-8?q?=C5?= =?utf-8?q?=BD?=", "Ž"),
        # An encoded word is one only as a whole word.
        ("x=?utf-8?q?a?=", "x=?utf-8?q?a?="),
        ("Dømi raw", "Dømi raw"),
    ],
)
def test_unstructured_text_reads_the_way_rfc_2047_says(body: str, text: str) -> None:
    assert read_unstructured(body) == text


@pytest.mark.parametrize(
    "body",
    [
        "=?utf-8?b?a?=",
        "=?utf-8?b?a$==?=",
        "=?utf-8?q?=ZZ?=",
        "=?utf-8?q?é?=",
        "=?no-such-charset?q?x?=",
        "=?utf-8?q?=FF?=",
        "=?utf-8?q?a?= =?latin-1?q?=FF?= =?utf-8?q?=FF?=",
    ],
)
def test_an_encoded_word_that_does_not_decode_is_a_value_error(body: str) -> None:
    with pytest.raises(ValueError, match="encoded word"):
        _ = read_unstructured(body)


@pytest.mark.parametrize(
    "charset", ["zlib", "zlib_codec", "bz2", "base64", "hex", "uu", "quopri", "rot13"]
)
def test_an_encoded_word_in_a_codec_that_is_not_a_text_encoding_does_not_decode(
    charset: str,
) -> None:
    """Such a codec turns bytes into other bytes — a decompressor among them — never text."""
    with pytest.raises(ValueError, match="encoded word"):
        _ = read_unstructured(f"=?{charset}?q?QUFB?=")


_ADDRESS_LISTS: list[tuple[str, list[ReadGroup]]] = [
    ("a@example.com", [(None, [""])]),
    ("<a@example.com>", [(None, [""])]),
    ("Alice <a@example.com>", [(None, ["Alice"])]),
    ('"Doe, Jane" <a@example.com>', [(None, ["Doe, Jane"])]),
    ('"a \\" b" <a@example.com>', [(None, ['a " b'])]),
    ("=?utf-8?q?=C5=BDlu=C5=A5?= <a@example.com>", [(None, ["Žluť"])]),
    ("=?utf-8?q?a?=\r\n =?utf-8?q?b?= <a@example.com>", [(None, ["ab"])]),
    ("Dømi <dømi@xn--dmi-0na.fo>", [(None, ["Dømi"])]),
    ("a@b.cz, Bob <b@b.cz>", [(None, [""]), (None, ["Bob"])]),
    ('"ex<amp>le"@example.com', [(None, [""])]),
    ('Jane <"ex<amp>le"@example.com>', [(None, ["Jane"])]),
    ("user@[IPv6:2001:db8::1]", [(None, [""])]),
    ("Tým: dømi@example.com;, a@b.cz", [("Tým", [""]), (None, [""])]),
    ("g: A <a@b.cz>, b@b.cz;", [("g", ["A", ""])]),
    ("nobody:;", [("nobody", [])]),
    ("=?utf-8?q?x?=: ;", [("x", [])]),
]


@pytest.mark.parametrize(("body", "read"), _ADDRESS_LISTS)
def test_an_address_list_reads_into_groups_and_display_names(
    body: str, read: list[ReadGroup]
) -> None:
    assert read_address_list(body) == read


@pytest.mark.parametrize(
    "body",
    [
        "a@b.cz)",
        "(comment) a@b.cz",
        "g: a@b.cz",
        "g: h: a@b.cz;;",
        '"open',
        "<a@b.cz",
        "<a@b.cz> <c@d.cz>",
        "A <a@b.cz> trailing",
        "a@b.cz;",
    ],
)
def test_an_address_list_the_reader_cannot_follow_is_a_value_error(body: str) -> None:
    with pytest.raises(ValueError, match="address list"):
        _ = read_address_list(body)
