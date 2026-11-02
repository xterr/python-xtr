"""Unstructured text as the engine writes it: plain where it can, encoded where it must."""

from __future__ import annotations

import re

import pytest

from tests.support.engine_cases import (
    CONTROL_CHARACTERS,
    LONG_NAME,
    LONG_SUBJECT,
    decode_field,
    lines_of,
    rfc2047,
)
from tests.support.wire import encoded_words, readings
from xtr_mime import _engine
from xtr_mime._engine._grammar import check_folded
from xtr_mime._engine._unstructured import write_text
from xtr_mime._header_reader import read_unstructured
from xtr_mime.exception import RfcComplianceError


def test_a_non_ascii_unstructured_header_is_an_encoded_word_that_decodes_back() -> None:
    field = _engine.fold_header("Subject", "Héllo wörld")

    assert "=?utf-8?" in field.lower()
    assert field.isascii()
    assert decode_field(field) == "Héllo wörld"


def test_an_ascii_unstructured_header_is_written_as_is() -> None:
    assert _engine.fold_header("X-Mailer", "plain value") == "X-Mailer: plain value"


def test_a_long_header_folds_into_crlf_lines_of_at_most_76_characters() -> None:
    field = _engine.fold_header("Subject", LONG_SUBJECT)

    lines = lines_of(field)
    assert len(lines) > 1
    assert all(len(line) <= 76 for line in lines)
    assert all(line.startswith(" ") for line in lines[1:])
    assert "\n" not in field.replace("\r\n", "")
    assert decode_field(field) == LONG_SUBJECT


LONG_UNSUBSCRIBE = "<https://example.com/u/" + "a" * 120 + ">"
LONG_VARIABLES = '{"k":"' + "v" * 200 + '"}'


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("List-Unsubscribe", LONG_UNSUBSCRIBE),
        ("X-Mailgun-Variables", LONG_VARIABLES),
        ("Subject", "x" * 300),
    ],
)
def test_an_ascii_word_too_long_for_a_line_is_written_plain_on_a_line_of_its_own(
    name: str, value: str
) -> None:
    assert _engine.fold_header(name, value) == f"{name}:\r\n {value}"


def test_a_short_ascii_value_stays_on_the_name_line() -> None:
    field = _engine.fold_header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click")

    assert field == "List-Unsubscribe-Post: List-Unsubscribe=One-Click"


@pytest.mark.parametrize("line_length", [997, 998])
def test_a_plain_word_may_fill_its_line_up_to_998_octets(line_length: int) -> None:
    word = "x" * (line_length - 1)

    field = _engine.fold_header("X-A", word)

    assert lines_of(field) == ["X-A:", f" {word}"]


def test_a_plain_word_that_would_make_a_line_of_999_octets_is_refused_without_quoting_it() -> None:
    word = "x" * 998

    with pytest.raises(RfcComplianceError, match="998") as raised:
        _ = _engine.fold_header("X-A", word)

    assert "xxxx" not in str(raised.value)


def test_only_the_non_ascii_words_of_a_text_with_a_long_token_are_encoded() -> None:
    token = "t" * 100
    value = f"hello there {token} and wörld after"

    field = _engine.fold_header("Subject", value)

    assert f"\r\n {token}\r\n" in field
    assert [rfc2047(word) for word in encoded_words(field)] == ["wörld"]
    assert decode_field(field) == value


def test_a_long_token_between_non_ascii_words_stays_plain() -> None:
    token = "t" * 100
    value = f"Žluťoučký kůň {token} úpěl"

    field = _engine.fold_header("Subject", value)

    assert f"\r\n {token}\r\n" in field
    assert rfc2047(field.split(":", 1)[1]).strip() == value


@pytest.mark.parametrize(
    "value",
    [
        "Žluťoučký kůň " + "t" * 100 + " úpěl",
        "a  Ž\tŽ  b =?x?= " + "t" * 80 + "\tc",
        LONG_SUBJECT,
    ],
)
def test_the_engine_written_text_decodes_back_with_its_ascii_words_plain(value: str) -> None:
    """What the engine writes when the package's folding would not read back, tried directly."""
    folded = write_text("Subject", value)

    check_folded(folded)
    field = folded.removesuffix("\r\n")
    # Whitespace around the value is dropped, as the package drops it.
    assert rfc2047(field.split(":", 1)[1]).strip() == value.strip()
    assert all(len(line) <= 76 for line in lines_of(field) if "t" * 80 not in line)
    plain = re.sub(r"=\?.+?\?=", "", field)
    assert all(word in plain for word in value.split() if word.isascii() and "=?" not in word)
    # Text a reader takes for an encoded word is encoded, so it reads back as written.
    assert "=?x?=" not in field


def test_a_line_break_in_a_value_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", "Hi\r\nBcc: victim@example.com")


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_unstructured_text_is_refused(control: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", f"Hi{control}there")


def test_a_tab_in_unstructured_text_is_kept() -> None:
    assert decode_field(_engine.fold_header("Subject", "a\tb")) == "a\tb"


def test_an_encoded_word_that_decodes_to_a_line_break_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Subject", "=?utf-8?q?Hi=0D=0ABcc:_x@example.com?=")


def test_an_encoded_word_in_unstructured_text_is_written_as_the_text_it_is() -> None:
    """The engine alone would decode ``=?...?=`` in a value; a reader must see the value."""
    field = _engine.fold_header("Subject", "=?utf-8?q?h=C3=A9llo?=")

    assert rfc2047(field.split(":", 1)[1]).strip() == "=?utf-8?q?h=C3=A9llo?="
    assert decode_field(field) == "=?utf-8?q?h=C3=A9llo?="


@pytest.mark.parametrize(
    "value",
    [
        # A lenient reader decodes the second one, after an invalid first: a line break.
        "t" * 80 + "=?utf-8?x?a?==?utf-8?q?=0D=0ABcc:_v@e.x?=",
        "=?utf-8?x?a?==?utf-8?q?hi?=",
        "t" * 80 + "=?utf-8?q?hi?=",
        "x=?utf-8?q?hi?=",
        "=?utf-8?q?hi?=x",
        "=?utf-8?q?a=?utf-8?q?b?=?=",
        "=?utf-8?q?a?==?utf-8?q?b?=",
        "=?utf-8?b?aGk=?=" + "t" * 80,
        "see " + "t" * 90 + "=?utf-8?q?hi?= now",
        "=?=?utf-8?q?hi?=?=",
    ],
)
def test_an_encoded_word_lookalike_inside_a_word_reads_back_literally_to_every_reader(
    value: str,
) -> None:
    """A word holding ``=?`` is encoded: no reader, however lenient, decodes a part of it."""
    field = _engine.fold_header("Subject", value)

    assert readings(field) == (value, value, value)


@pytest.mark.parametrize(
    "token",
    [
        "<https://example.com/unsubscribe?list=news&token=" + "a" * 80 + "&x=y?>",
        '{"id":"' + "a" * 80 + '","q":"?=","e":"x="}',
    ],
)
def test_a_long_word_without_an_encoded_word_opening_stays_plain(token: str) -> None:
    field = _engine.fold_header("List-Unsubscribe", token)

    assert f"\r\n {token}" in field
    assert readings(field) == (token, token, token)


@pytest.mark.parametrize("subject", [LONG_NAME, "a  Ž  b", "Ž\tŽ", "Ž lead", "x" * 200 + " Ž"])
def test_an_unstructured_value_decodes_back_exactly_as_rfc_2047_reads_it(subject: str) -> None:
    field = _engine.fold_header("Subject", subject)

    assert rfc2047(field.split(":", 1)[1]).strip() == subject


def test_an_encoded_word_naming_a_codec_that_is_not_text_is_written_as_the_text_it_is() -> None:
    value = "=?utf-8?q?=3D=3Fzlib=3Fq=3Fx=3F=3D?="

    field = _engine.fold_header("Subject", value)

    assert read_unstructured(field.removeprefix("Subject:")) == value
