"""A header written as it was folded, byte for byte: what a signature covering it needs."""

from __future__ import annotations

import pytest

from xtr_mime import Headers, Message, TextPart
from xtr_mime.exception import RfcComplianceError
from xtr_mime.header import FoldedHeader, UnstructuredHeader

_FIELD = "DKIM-Signature: v=1; a=rsa-sha256; d=example.com;\r\n s=default;  h=From:To;\r\n\tb=abc"


def test_it_is_written_exactly_as_it_was_folded() -> None:
    assert FoldedHeader(_FIELD).to_string() == _FIELD


def test_a_final_line_break_is_not_part_of_the_field() -> None:
    assert FoldedHeader(_FIELD + "\r\n").to_string() == _FIELD


def test_its_name_is_what_comes_before_the_first_colon() -> None:
    assert FoldedHeader(_FIELD).get_name() == "DKIM-Signature"


def test_its_value_is_the_field_unfolded() -> None:
    assert FoldedHeader(_FIELD).get_value() == (
        "v=1; a=rsa-sha256; d=example.com; s=default;  h=From:To;\tb=abc"
    )


def test_it_is_a_text_header() -> None:
    assert isinstance(FoldedHeader(_FIELD), UnstructuredHeader)


def test_a_message_renders_it_as_it_was_folded() -> None:
    headers = Headers(FoldedHeader(_FIELD)).add_mailbox_list_header("From", ["a@example.com"])
    message = Message(headers.add_mailbox_list_header("To", ["b@example.com"]), TextPart("x"))

    assert f"\r\n{_FIELD}\r\n".encode() in b"\r\n" + b"".join(message.to_iterable())


def test_setting_another_value_drops_the_folding() -> None:
    header = FoldedHeader(_FIELD)

    header.set_value("v=2")

    assert header.to_string() == "DKIM-Signature: v=2"


@pytest.mark.parametrize(
    "rest",
    [
        "\r\nBcc: victim@example.com",
        "\nBcc: victim@example.com",
        "\rBcc: victim@example.com",
        "\r\n\r\nvictim",
        "\x00victim",
        "\u2028victim",
        "victim" * 200,
    ],
    ids=["header", "line feed", "carriage return", "empty line", "null", "separator", "long"],
)
def test_a_field_that_is_not_one_folded_header_is_refused_without_being_repeated(
    rest: str,
) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = FoldedHeader(f"X-A: {'a' * 64}{rest}")

    assert "victim" not in str(caught.value)


@pytest.mark.parametrize("field", ["no colon at all", ": no name", "X A: a space", "Xé: a"])
def test_a_field_without_a_header_name_is_refused(field: str) -> None:
    with pytest.raises(RfcComplianceError, match="header name"):
        _ = FoldedHeader(field)


@pytest.mark.parametrize("blank", [" ", "\t", " \t "], ids=["space", "tab", "spaces and tab"])
def test_a_continuation_line_of_whitespace_only_is_refused(blank: str) -> None:
    with pytest.raises(RfcComplianceError, match="not a continuation"):
        _ = FoldedHeader(f"X-A: v\r\n{blank}\r\n x")
