"""The grammar every field is held to: names, folded lines, identifiers and boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.engine_cases import SEPARATORS
from xtr_mime import _engine
from xtr_mime._engine._grammar import (
    check_boundary,
    check_folded,
    check_message_id,
    check_name,
    check_token,
    join_blank_lines,
    refuse_forbidden,
)
from xtr_mime._engine._values import MessageIds
from xtr_mime.exception import RfcComplianceError

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize("name", ["", "Sub ject", "Sub\tject", "Sub\r\nject", "Šubject", "a\x7f"])
def test_a_header_name_that_is_not_printable_ascii_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="header name"):
        _ = _engine.fold_header(name, "value")


def test_a_continuation_line_without_leading_space_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="continuation"):
        check_folded("Subject: a\r\nBcc: victim@example.com\r\n")


def test_a_folded_field_must_end_with_its_line_break() -> None:
    with pytest.raises(RfcComplianceError, match="continuation"):
        check_folded("Subject: a\nBcc: victim@example.com")


@pytest.mark.parametrize("character", ["\x00", "\x0b", "\x0c", "\x1c", "\x7f", *SEPARATORS])
def test_a_folded_field_holding_a_control_character_is_refused(character: str) -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        check_folded(f"Subject: a{character}Bcc: victim@example.com\r\n")


def test_a_folded_field_keeps_its_tabs() -> None:
    check_folded("Subject: a\tb\r\n\tc\r\n")


def test_a_folded_line_longer_than_998_octets_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="998"):
        check_folded("Subject: " + "ø" * 500 + "\r\n")


def test_a_refused_value_is_repeated_whole_and_escaped_when_short() -> None:
    with pytest.raises(RfcComplianceError) as raised:
        refuse_forbidden("The X-A header", "a\r\nb")

    assert str(raised.value).endswith(": '\\r' in \"a\\r\\nb\".")


def test_a_refused_value_is_cut_to_its_first_64_characters() -> None:
    value = "a" * 1000 + "\nBcc: victim@example.com"

    with pytest.raises(RfcComplianceError) as raised:
        refuse_forbidden("The X-A header", value)

    message = str(raised.value)
    assert message.endswith(": '\\n' in \"" + "a" * 64 + '…".')
    assert "a" * 65 not in message


@pytest.mark.parametrize(
    "identifier",
    ["a@b", "a.b+&%$.c@d", "a@b.c+&%$.d", '"ab"@c', '"a@b"@c', "a@[1.2.3.4]", "a@[x:y]"],
)
def test_an_identifier_of_the_msg_id_grammar_is_accepted(identifier: str) -> None:
    _engine.check_message_id(identifier)

    assert _engine.header_body("Message-ID", MessageIds((identifier,))) == f"<{identifier}>"


@pytest.mark.parametrize(
    "identifier",
    [
        "abc",
        "a@b@c",
        "a..b@c",
        ".a@c",
        "a@b.",
        '"a\\<\\>b"@c',
        '"a<b"@c',
        '"a b"@c',
        '""@c',
        "a@[x<y]",
        "a@[x\\y]",
        "a@b c",
        "a@é",
    ],
)
def test_an_identifier_outside_the_msg_id_grammar_is_refused(identifier: str) -> None:
    with pytest.raises(RfcComplianceError, match="identifier"):
        _engine.check_message_id(identifier)


@pytest.mark.parametrize(
    "boundary",
    ["", "a" * 71, "trailing ", 'a"b', "a\r\nb", "é", "a;b", "a\tb", "a@b", "=?x?=", "a=?b"],
)
def test_a_boundary_outside_rfc_2046_is_refused(boundary: str) -> None:
    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.build_multipart("mixed", boundary, [])


@pytest.mark.parametrize("boundary", ["a" * 70, "with inner space", "'()+_,-./:?=09AZaz"])
def test_a_boundary_inside_rfc_2046_is_kept(boundary: str) -> None:
    assert _engine.build_multipart("mixed", boundary, []).get_boundary() == boundary


_LONG = "a" * 10_000 + " \r\nBcc: victim@example.com"


def _token(value: str) -> None:
    check_token("charset", value)


def _folded(value: str) -> None:
    check_folded(f"X-A: a\r\nB{value}\r\n")


_CHECKS: list[Callable[[str], None]] = [
    check_name,
    check_message_id,
    check_boundary,
    _token,
    _folded,
]


@pytest.mark.parametrize(
    "check", _CHECKS, ids=["name", "message id", "boundary", "token", "folded"]
)
def test_a_refused_value_is_shown_cut_to_its_first_64_characters(
    check: Callable[[str], None],
) -> None:
    with pytest.raises(RfcComplianceError) as raised:
        check(_LONG)

    message = str(raised.value)
    assert "a…" in message
    assert "a" * 65 not in message
    assert "victim" not in message
    assert "\r" not in message
    assert "\n" not in message


@pytest.mark.parametrize(
    ("folded", "joined"),
    [
        ("X-A: a\r\n b\r\n", "X-A: a\r\n b\r\n"),
        ("X-A: a\r\n   \r\n b\r\n", "X-A: a\r\n    b\r\n"),
        ("X-A: a\r\n \r\n\t\r\n b\r\n", "X-A: a\r\n \t b\r\n"),
        ("X-A: a\r\n b\r\n   \r\n", "X-A: a\r\n b   \r\n"),
        ("X-A: a\r\n   ", "X-A: a\r\n   "),
    ],
    ids=["none", "between", "two between", "last", "unterminated"],
)
def test_a_line_of_whitespace_alone_joins_the_line_after_it(folded: str, joined: str) -> None:
    assert join_blank_lines(folded) == joined


def test_joining_keeps_what_the_field_unfolds_to() -> None:
    folded = "Subject: Invoice\r\n" + " " * 72 + "\r\n #123\r\n"

    joined = join_blank_lines(folded)

    assert joined.replace("\r\n", "") == folded.replace("\r\n", "")
    check_folded(joined)
