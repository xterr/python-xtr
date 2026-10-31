from __future__ import annotations

import re
from typing import ClassVar

import pytest

from tests.support.wire import assert_folded, decode, encoded_words
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import UnstructuredHeader

# Upstream writes the byte 0x8F in iso-8859-1. Values are text here, where U+008F is a C1
# control the engine refuses, so a letter outside ASCII stands in for it.
NON_ASCII = "\xf8"

LONG_SUBJECT = "Žluťoučký kůň úpěl ďábelské ódy, " * 4

# Values a reader must see as written: no encoded word for a long ASCII token.
READABLE = [
    ("List-Unsubscribe", "<https://example.com/u/" + "a" * 120 + ">"),
    ("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"),
    ("X-Mailgun-Variables", '{"k":"' + "v" * 200 + '"}'),
    ("Subject", "x" * 300),
]


def test_the_name_is_returned_verbatim() -> None:
    assert UnstructuredHeader("Subject", "").get_name() == "Subject"


def test_the_value_is_returned_verbatim() -> None:
    assert UnstructuredHeader("Subject", "Test").get_value() == "Test"


def test_the_basic_structure_is_a_key_value_pair() -> None:
    assert UnstructuredHeader("Subject", "Test").to_string() == "Subject: Test"


def test_long_headers_are_folded_at_a_word_boundary() -> None:
    value = (
        "The quick brown fox jumped over the fence, he was a very very "
        "scary brown fox with a bushy tail"
    )

    rendered = UnstructuredHeader("X-Custom-Header", value).to_string()

    # Plain ASCII the engine folds deterministically: the exact bytes are kept.
    assert rendered == (
        "X-Custom-Header: The quick brown fox jumped over the fence, he was a very\r\n"
        " very scary brown fox with a bushy tail"
    )


@pytest.mark.parametrize(("name", "value"), READABLE)
def test_an_ascii_value_is_written_plain_however_long_its_words(name: str, value: str) -> None:
    rendered = UnstructuredHeader(name, value).to_string()

    assert not encoded_words(rendered)
    assert rendered.replace("\r\n", "").split(":", 1)[1].strip() == value


@pytest.mark.parametrize(("name", "value"), READABLE)
def test_the_body_of_an_ascii_value_is_the_value_whatever_the_name(name: str, value: str) -> None:
    assert UnstructuredHeader(name, value).get_body_as_string() == value
    assert UnstructuredHeader(f"h:{name}", value).get_body_as_string() == value


def test_printable_ascii_only_appears_in_headers() -> None:
    rendered = UnstructuredHeader("X-Test", NON_ASCII).to_string()

    assert re.fullmatch(r"[^:\x00-\x20\x80-\xff]+: [^\x80-\xff\r\n]+", rendered)


def test_encoded_words_follow_the_general_structure() -> None:
    rendered = UnstructuredHeader("X-Test", NON_ASCII).to_string()

    assert re.fullmatch(r"X-Test: =\?.*?\?.*?\?.*?\?=", rendered, re.DOTALL)


def test_an_encoded_word_carries_its_charset_and_decodes_back() -> None:
    header = UnstructuredHeader("X-Test", NON_ASCII)
    header.set_charset("iso-8859-1")

    rendered = header.to_string()

    # Adapted (D1): the engine writes every encoded word in UTF-8, whatever charset is set,
    # and picks Q or B itself; what a reader gets back is what was set.
    assert re.fullmatch(r"X-Test: =\?utf-8\?[qb]\?.+\?=", rendered)
    assert decode(rendered) == NON_ASCII


@pytest.mark.parametrize("byte", [*range(0x09), *range(0x0A, 0x20), 0x7F])
def test_a_non_printable_ascii_character_is_refused(byte: int) -> None:
    header = UnstructuredHeader("X-A", chr(byte))

    # Adapted: upstream writes these as encoded words; the engine refuses every control but
    # TAB outright, since some readers decode one into a line break that starts a header.
    with pytest.raises(RfcComplianceError):
        _ = header.to_string()


# Adapted: 0x80-0x9F are C1 controls as characters, refused below; the rest are encoded.
@pytest.mark.parametrize("byte", range(0xA0, 0x100))
def test_eight_bit_characters_are_encoded(byte: int) -> None:
    header = UnstructuredHeader("X-A", chr(byte))
    header.set_charset("iso-8859-1")

    rendered = header.to_string()

    # Adapted (D1): decode and compare instead of the iso-8859-1 Q bytes.
    assert rendered.isascii()
    assert encoded_words(rendered)
    assert decode(rendered) == chr(byte)


@pytest.mark.parametrize("byte", range(0x80, 0xA0))
def test_a_c1_control_character_is_refused(byte: int) -> None:
    header = UnstructuredHeader("X-A", chr(byte))

    # Adapted: NEL (0x85) ends a line for some readers; the engine refuses every C1 control.
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = header.to_string()


def test_encoded_words_are_no_more_than_75_characters_per_line() -> None:
    header = UnstructuredHeader("X-Test", LONG_SUBJECT)

    rendered = header.to_string()

    # Adapted (D1): any long value, then the RFC 2047 limits, then decode and compare.
    assert all(len(word) <= 75 for word in encoded_words(rendered))
    assert_folded(rendered)
    assert decode(rendered) == LONG_SUBJECT


def test_a_line_break_in_the_value_is_refused() -> None:
    header = UnstructuredHeader("X-Test", f"{NON_ASCII}line_one_here\r\nline_two_here")

    # Adapted: upstream encodes the line break into the words; the engine refuses it.
    with pytest.raises(RfcComplianceError):
        _ = header.to_string()


def test_fwsp_is_used_when_the_encoded_value_needs_several_lines() -> None:
    rendered = UnstructuredHeader("X-Test", LONG_SUBJECT).to_string()

    # Adapted (D1): the folding rules instead of the folding points.
    assert len(rendered.split("\r\n")) > 1
    assert_folded(rendered)


def test_adjacent_words_are_encoded_together() -> None:
    word = f"w{NON_ASCII}rd"
    text = f"start {word} {word} then {word}"

    rendered = UnstructuredHeader("X-Test", text).to_string()

    # Adapted (D1): no space inside an encoded word, and the text reads back whole.
    assert all(" " not in encoded for encoded in encoded_words(rendered))
    assert decode(rendered) == text


@pytest.mark.parametrize("value", ["Fabïen  Pötencier  Länge", "Fabïen \t Pötencier"])
def test_whitespace_runs_between_encoded_words_are_kept(value: str) -> None:
    rendered = UnstructuredHeader("Subject", value).to_string()

    # Adapted (D1): a reader would drop the whitespace between two encoded words; it must
    # read back as it was.
    assert decode(rendered) == value


def test_the_language_is_kept_though_the_engine_does_not_write_it() -> None:
    value = f"fo{NON_ASCII}bar"
    header = UnstructuredHeader("Subject", value)
    header.set_language("en")
    header.set_charset("iso-8859-1")

    rendered = header.to_string()

    # Adapted (D1): the engine has no RFC 2231 language in encoded words; the text reads back.
    assert header.get_language() == "en"
    assert decode(rendered) == value


def test_set_body() -> None:
    header = UnstructuredHeader("X-Test", "")

    header.set_body("test")

    assert header.get_value() == "test"


def test_set_body_refuses_what_is_not_text() -> None:
    header = UnstructuredHeader("X-Test", "")

    with pytest.raises(InvalidArgumentError):
        header.set_body(42)


def test_get_body() -> None:
    assert UnstructuredHeader("Subject", "test").get_body() == "test"


def test_set_value() -> None:
    header = UnstructuredHeader("Subject", "a")

    header.set_value("b")

    assert header.get_body() == "b"


def test_the_class_can_be_extended() -> None:
    class TagHeader(UnstructuredHeader):
        __slots__: ClassVar[tuple[str, ...]] = ()

    assert TagHeader("X-Tag", "password-reset").to_string() == "X-Tag: password-reset"
