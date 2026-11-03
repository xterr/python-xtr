"""Parts built from leaves, multiparts around them, and whole messages around a body."""

from __future__ import annotations

import base64
import quopri
from email.message import EmailMessage
from typing import TYPE_CHECKING

import pytest

from tests.support.engine_cases import text_leaf
from tests.support.growth import assert_linear_growth
from xtr_mime import _engine
from xtr_mime._engine import BinaryLeaf, Mailbox, Parameterized
from xtr_mime._engine._policy import POLICY
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError

if TYPE_CHECKING:
    from xtr_mime._engine._values import TransferEncoding


@pytest.mark.parametrize("encoding", ["quoted-printable", "base64", "8bit", "7bit"])
def test_a_text_leaf_honours_the_requested_transfer_encoding(encoding: TransferEncoding) -> None:
    content = "Hello" if encoding == "7bit" else "Héllo wörld"

    part = _engine.build_text(text_leaf(content, transfer_encoding=encoding))

    assert part["Content-Transfer-Encoding"] == encoding
    # Inside base64 the engine encodes CRLF line ends, which decoding keeps.
    assert part.get_content() == content + ("\r\n" if encoding == "base64" else "\n")


def test_a_text_leaf_body_is_encoded_on_the_wire() -> None:
    raw = _engine.to_bytes(_engine.build_text(text_leaf("Héllo", transfer_encoding="base64")))
    qp = _engine.to_bytes(_engine.build_text(text_leaf("Héllo")))
    eight = _engine.to_bytes(_engine.build_text(text_leaf("Héllo", transfer_encoding="8bit")))

    assert base64.b64decode(raw.split(b"\r\n\r\n", 1)[1]) == b"H\xc3\xa9llo\r\n"
    assert quopri.decodestring(qp.split(b"\r\n\r\n", 1)[1]) == b"H\xc3\xa9llo\r\n"
    assert eight.split(b"\r\n\r\n", 1)[1] == b"H\xc3\xa9llo\r\n"


def test_a_text_leaf_always_ends_with_a_line_break() -> None:
    part = _engine.build_text(text_leaf("no newline"))

    assert part.get_content() == "no newline\n"


def test_a_text_leaf_carries_its_charset_and_extra_parameters() -> None:
    part = _engine.build_text(
        text_leaf("Ahoj", subtype="html", charset="iso-8859-2", parameters={"name": "ahoj.html"})
    )

    assert part.get_content_type() == "text/html"
    assert part.get_param("charset") == "iso-8859-2"
    assert part.get_param("name") == "ahoj.html"
    assert list(part.keys())[:2] == ["Content-Type", "Content-Transfer-Encoding"]


def test_a_text_leaf_in_a_charset_python_does_not_know_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="no-such-charset"):
        _ = _engine.build_text(text_leaf(charset="no-such-charset"))


@pytest.mark.parametrize(
    "charset",
    ["utf-8\n", "utf-8\r\n", "utf-8\x0b", "utf-8\x0c", "utf-8\x1c", "utf-8\x00", "utf 8", ""],
)
def test_a_charset_that_is_not_a_token_is_refused(charset: str) -> None:
    with pytest.raises(RfcComplianceError, match="charset"):
        _ = _engine.build_text(text_leaf(charset=charset))


def test_a_text_leaf_its_charset_cannot_hold_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="us-ascii"):
        _ = _engine.build_text(text_leaf("Žluť", charset="us-ascii"))


def test_a_seven_bit_text_leaf_with_non_ascii_content_is_an_invalid_argument() -> None:
    with pytest.raises(InvalidArgumentError, match="7bit"):
        _ = _engine.build_text(text_leaf("Žluť", transfer_encoding="7bit"))


def test_a_text_leaf_can_be_an_attachment() -> None:
    part = _engine.build_text(
        text_leaf(disposition=Parameterized("attachment", {"name": "hello.txt"}))
    )

    assert part.get_content_disposition() == "attachment"
    assert part.get_param("name", header="Content-Disposition") == "hello.txt"


def test_a_binary_leaf_keeps_an_inline_disposition_and_its_content_id() -> None:
    part = _engine.build_binary(
        BinaryLeaf(
            content=b"\x89PNG\x00\xff",
            maintype="image",
            subtype="png",
            transfer_encoding="base64",
            disposition=Parameterized("inline", {"filename": "logo.png"}),
            content_id="logo@xtr",
        )
    )

    assert part.get_content_type() == "image/png"
    assert part.get_content_disposition() == "inline"
    assert part.get_filename() == "logo.png"
    assert part["Content-ID"] == "<logo@xtr>"
    assert part.get_content() == b"\x89PNG\x00\xff"


def test_a_long_content_id_is_written_whole_on_the_wire() -> None:
    identifier = "c" * 90 + "@example.com"
    leaf = BinaryLeaf(
        content=b"x",
        maintype="image",
        subtype="png",
        transfer_encoding="base64",
        content_id=identifier,
    )

    raw = _engine.to_bytes(_engine.build_binary(leaf))

    assert f"\r\nContent-ID: <{identifier}>\r\n".encode() in raw


@pytest.mark.parametrize("token", ["", "pl ain", "pl\r\nain", "a/b", "é", "x;y"])
def test_a_media_type_part_that_is_not_a_token_is_refused(token: str) -> None:
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_binary(
            BinaryLeaf(content=b"x", maintype=token, subtype="x", transfer_encoding="base64")
        )
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_binary(
            BinaryLeaf(content=b"x", maintype="x", subtype=token, transfer_encoding="base64")
        )
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_text(text_leaf(subtype=token))
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.build_multipart(token, "boundary", [])


@pytest.mark.parametrize("encoding", ["quoted-printable", "base64", "8bit"])
def test_a_binary_leaf_honours_the_requested_transfer_encoding(encoding: TransferEncoding) -> None:
    part = _engine.build_binary(
        BinaryLeaf(
            content=b"plain bytes",
            maintype="application",
            subtype="x-thing",
            transfer_encoding=encoding,
            parameters={"name": "thing.bin"},
        )
    )

    assert part["Content-Transfer-Encoding"] == encoding
    assert part.get_param("name") == "thing.bin"
    assert part.get_content() == b"plain bytes"


def test_a_binary_quoted_printable_line_may_run_to_77_characters() -> None:
    """The engine's binary quoted-printable writer (``binascii.b2a_qp``) may break the 76 limit.

    A line feed right after 76 bytes gets a soft break after the 76th character, so that line
    is 77 long. Readers accept it; whether or not the release still does it, no line runs
    longer and the body decodes back.
    """
    content = b"a" * 76 + b"\n"
    leaf = BinaryLeaf(
        content=content, maintype="application", subtype="x", transfer_encoding="quoted-printable"
    )

    raw = _engine.to_bytes(_engine.build_binary(leaf))

    body = raw.split(b"\r\n\r\n", 1)[1]
    assert max(len(line) for line in body.split(b"\r\n")) <= 77
    assert quopri.decodestring(body) == content


def test_a_text_typed_binary_leaf_carries_no_charset() -> None:
    part = _engine.build_binary(
        BinaryLeaf(content=b"raw", maintype="text", subtype="plain", transfer_encoding="base64")
    )

    assert part.get_content_type() == "text/plain"
    assert part.get_param("charset") is None
    assert part["Content-Transfer-Encoding"] == "base64"


def test_a_seven_bit_binary_leaf_with_eight_bit_bytes_is_an_invalid_argument() -> None:
    leaf = BinaryLeaf(
        content=b"\xff", maintype="application", subtype="x", transfer_encoding="7bit"
    )

    with pytest.raises(InvalidArgumentError, match="7bit"):
        _ = _engine.build_binary(leaf)


def test_the_engine_content_setter_adds_a_mime_version() -> None:
    message = EmailMessage(policy=POLICY)
    message.set_content("x")

    assert message["MIME-Version"] == "1.0"


def test_a_leaf_drops_the_mime_version_the_setter_added() -> None:
    assert _engine.build_text(text_leaf())["MIME-Version"] is None
    binary = _engine.build_binary(
        BinaryLeaf(content=b"x", maintype="application", subtype="x", transfer_encoding="base64")
    )
    assert binary["MIME-Version"] is None


def test_a_multipart_uses_the_supplied_boundary_and_strips_sub_part_mime_versions() -> None:
    parsed_child = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    multipart = _engine.build_multipart(
        "mixed", "b0und4ry_x", [_engine.build_text(text_leaf()), parsed_child]
    )

    raw = _engine.to_bytes(multipart)
    assert multipart.get_boundary() == "b0und4ry_x"
    assert raw.count(b"--b0und4ry_x\r\n") == 2
    assert raw.endswith(b"--b0und4ry_x--\r\n")
    assert b"MIME-Version" not in raw


def test_set_fields_carries_each_field_as_written_in_place_of_the_part_headers() -> None:
    part = _engine.build_text(text_leaf())

    _engine.set_fields(part, ["X-Written: as\r\n given", "Content-Type: text/plain"])

    rendered = _engine.to_bytes(part)
    assert rendered.startswith(b"X-Written: as\r\n given\r\nContent-Type: text/plain\r\n\r\n")


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("X-Written", id="no colon"),
        pytest.param("X Written: value", id="not a name"),
        pytest.param("X-Written: a\r\nInjected: 1", id="a line of its own"),
        pytest.param("X-Written: a\x00b", id="a control character"),
    ],
)
def test_set_fields_refuses_a_field_that_is_not_one(field: str) -> None:
    part = _engine.build_text(text_leaf())

    with pytest.raises(RfcComplianceError):
        _engine.set_fields(part, [field])


def test_prepend_fields_puts_the_fields_before_the_headers_the_part_carries() -> None:
    part = _engine.build_text(text_leaf())
    _engine.set_fields(part, ["Content-Type: text/plain"])

    _engine.prepend_fields(part, ["Subject: first", "X-A: second"])

    rendered = _engine.to_bytes(part)
    assert rendered.startswith(b"Subject: first\r\nX-A: second\r\nContent-Type: text/plain\r\n\r\n")


def _fields(size: int) -> list[str]:
    """``size`` fields, each of a name no other has."""
    return [f"X-{index}: a" for index in range(size)]


def test_set_fields_replaces_headers_of_distinct_names_in_time_linear_in_them() -> None:
    def replace(size: int) -> None:
        part = _engine.build_verbatim(b"")
        _engine.set_fields(part, _fields(size))
        _engine.set_fields(part, ["X-A: b"])

    _ = assert_linear_growth(replace, 5_000)


def test_prepend_fields_before_headers_of_distinct_names_takes_time_linear_in_them() -> None:
    def prepend(size: int) -> int:
        part = _engine.build_verbatim(b"")
        _engine.set_fields(part, _fields(size))
        _engine.prepend_fields(part, ["Subject: first"])
        return len(part)

    assert assert_linear_growth(prepend, 5_000) == 20_001


def test_prepend_fields_refuses_a_field_that_is_not_one() -> None:
    part = _engine.build_text(text_leaf())

    with pytest.raises(RfcComplianceError):
        _engine.prepend_fields(part, ["X-Written: a\r\nInjected: 1"])


def test_a_message_puts_its_own_headers_before_the_body_headers() -> None:
    body = _engine.build_text(text_leaf())

    message = _engine.build_message(
        [("MIME-Version", "1.0"), ("Subject", "Héllo"), ("To", [Mailbox("", "b@example.com")])],
        body,
    )

    assert list(message.keys()) == [
        "MIME-Version",
        "Subject",
        "To",
        "Content-Type",
        "Content-Transfer-Encoding",
    ]
    assert message.get_content() == "Hello\n"


def test_a_message_around_a_parsed_body_carries_one_mime_version() -> None:
    body = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    message = _engine.build_message([("MIME-Version", "1.0"), ("Subject", "x")], body)

    assert list(message.keys()) == ["MIME-Version", "Subject", "Content-Type"]
    assert _engine.to_bytes(message).count(b"MIME-Version") == 1


def test_a_message_keeps_the_body_mime_version_when_it_sets_none() -> None:
    body = _engine.parse(b"MIME-Version: 1.0\r\nContent-Type: text/plain\r\n\r\nhi\r\n")

    message = _engine.build_message([("Subject", "x")], body)

    assert list(message.keys()) == ["Subject", "MIME-Version", "Content-Type"]


def test_a_message_does_not_share_the_body_part_list() -> None:
    body = _engine.build_multipart("mixed", "b", [_engine.build_text(text_leaf())])

    message = _engine.build_message([], body)
    message.attach(_engine.build_text(text_leaf()))

    assert len(list(body.iter_parts())) == 1
    assert len(list(message.iter_parts())) == 2
