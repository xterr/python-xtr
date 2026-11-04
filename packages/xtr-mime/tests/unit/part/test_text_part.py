"""A text part: its body, its prepared headers and the transfer encoding it is written in.

Upstream's serialization cases have no counterpart (a part is not serialized; xtr-mailer
carries a queued email as plain data), nor have its custom encoders (encoding is the
engine's work).
"""

from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.rendered_part import decoded_body, read_part
from tests.support.wire import decode_parameters
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.header import Headers, ParameterizedHeader, UnstructuredHeader
from xtr_mime.part import File, TextPart

if TYPE_CHECKING:
    from xtr_mime.header import HeaderInterface

FIXTURES: Final = Path(__file__).parents[2] / "fixtures"


def _headers(*headers: HeaderInterface) -> list[str]:
    return Headers(*headers).to_array()


def _body(part: TextPart) -> bytes:
    return b"".join(part.body_to_iterable())


def test_constructor() -> None:
    part = TextPart("content")

    assert part.get_body() == "content"
    # Adapted (D1): the engine ends a text body with a line break.
    assert part.body_to_string() == "content\r\n"
    assert _body(part) == b"content\r\n"
    # body_to_iterable() can be called several times.
    assert _body(part) == b"content\r\n"
    assert part.get_media_type() == "text"
    assert part.get_media_subtype() == "plain"
    assert TextPart("content", None, "html").get_media_subtype() == "html"


def test_constructor_with_a_binary_file() -> None:
    part = TextPart(io.BytesIO(b"content"))

    assert part.get_body() == b"content"
    # Adapted (D1): the engine ends a text body with a line break, a CRLF.
    assert decoded_body(part) == b"content\r\n"
    assert decoded_body(part) == b"content\r\n"


def test_a_stream_is_read_from_its_start_when_it_can_seek() -> None:
    stream = io.BytesIO(b"content")
    _ = stream.read()

    assert TextPart(stream).get_body() == b"content"


def test_constructor_with_file() -> None:
    part = TextPart(File(FIXTURES / "content.txt"))

    assert part.get_body() == b"content"
    assert decoded_body(part) == b"content\r\n"


def test_constructor_with_unknown_file() -> None:
    path = str(FIXTURES / "unknown.txt")
    # The file is read only when the body is.
    part = TextPart(File(path))

    with pytest.raises(InvalidArgumentError) as caught:
        _ = part.get_body()

    assert str(caught.value) == (
        f'Unable to open path "{path}": Failed to open stream: No such file or directory.'
    )


def test_a_file_that_disappears_fails_when_rendered() -> None:
    part = TextPart(File(FIXTURES / "unknown.txt"))

    with pytest.raises(InvalidArgumentError, match="Failed to open stream"):
        _ = part.to_string()


def test_a_path_with_a_null_byte_is_refused_with_the_path_escaped() -> None:
    part = TextPart(File("/no/such\r\nfile\x00.txt"))

    with pytest.raises(InvalidArgumentError) as caught:
        _ = part.get_body()

    assert str(caught.value) == (
        'Unable to open path "/no/such\\r\\nfile\\x00.txt": Failed to open stream: '
        "embedded null byte."
    )


def test_constructor_with_a_directory() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TextPart(File(FIXTURES))

    assert str(caught.value) == f'Path "{FIXTURES}" is not readable.'


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs file permissions")
def test_constructor_with_an_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "secret.txt"
    _ = path.write_text("secret")
    path.chmod(0)

    with pytest.raises(InvalidArgumentError) as caught:
        _ = TextPart(File(path))

    assert str(caught.value) == f'Path "{path}" is not readable.'


def test_constructor_with_non_string_or_resource() -> None:
    with pytest.raises(TypeError) as caught:
        _ = TextPart(cast("str", object()))

    assert str(caught.value) == (
        'The body of "xtr_mime.part.TextPart" must be a string, bytes, a binary file or an '
        'instance of "xtr_mime.part.File" (got "object").'
    )


def test_headers() -> None:
    assert TextPart("content").get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/plain", {"charset": "utf-8"}),
        UnstructuredHeader("Content-Transfer-Encoding", "quoted-printable"),
    )
    assert TextPart("content", "iso-8859-1").get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/plain", {"charset": "iso-8859-1"}),
        UnstructuredHeader("Content-Transfer-Encoding", "quoted-printable"),
    )


def test_encoding() -> None:
    part = TextPart("content", "utf-8", "plain", "base64")

    # Adapted (D1): the engine encodes the text with its final line break, a CRLF.
    assert base64.b64decode(part.body_to_string()) == b"content\r\n"
    assert base64.b64decode(_body(part)) == b"content\r\n"
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/plain", {"charset": "utf-8"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
    )


def test_binary_encoding() -> None:
    body = b"raw\x00binary\x01payload"
    part = TextPart(body, None, "plain", "binary")

    assert part.body_to_string().encode("utf-8", "surrogateescape") == body
    assert _body(part) == body
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/plain"),
        UnstructuredHeader("Content-Transfer-Encoding", "binary"),
    )


def test_binary_encoding_with_resource_containing_high_bytes() -> None:
    body = b"\xff\xfe\x80\x00\x7f\xc3\xa9"
    part = TextPart(io.BytesIO(body), None, "plain", "binary")

    assert part.body_to_string().encode("utf-8", "surrogateescape") == body
    assert _body(part) == body


def test_binary_encoding_keeps_the_charset() -> None:
    part = TextPart("été", "utf-8", "plain", "binary")

    assert _body(part) == "été".encode()
    assert decode_parameters(part.get_prepared_headers().to_array()[0]) == {"charset": "utf-8"}


def test_an_unknown_encoding_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = TextPart("content", "utf-8", "plain", "this_encoding_does_not_exist")

    assert str(caught.value) == (
        'The encoding must be one of "quoted-printable", "base64", "8bit", "binary" '
        '("this_encoding_does_not_exist" given).'
    )


def test_a_text_body_given_as_bytes_is_read_in_its_charset() -> None:
    part = TextPart("été".encode("iso-8859-1"), "iso-8859-1")

    assert read_part(part).get_content() == "été\r\n"


def test_a_body_in_an_unknown_charset_is_refused_with_the_charset_escaped() -> None:
    part = TextPart(b"content", "no\r\nsuch")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = part.to_string()

    assert str(caught.value) == 'The body is not "no\\r\\nsuch" text: no codec goes by that name.'


def test_a_body_in_a_charset_holding_a_null_byte_is_refused() -> None:
    part = TextPart("content", "utf-8\x00")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = part.to_string()

    assert str(caught.value) == 'The body is not "utf-8\\x00" text: embedded null character.'


def test_a_body_that_is_not_in_its_charset_is_refused() -> None:
    part = TextPart(b"\xff", "utf-8")

    with pytest.raises(InvalidArgumentError, match='not "utf-8"'):
        _ = part.to_string()


def test_a_content_type_parameter_name_too_long_for_a_line_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="at most 40 characters"):
        _ = TextPart("x").set_content_type_parameter("x" * 80, "v")


def test_a_text_body_without_charset_is_written_in_utf8() -> None:
    assert decoded_body(TextPart("été", None)) == "été".encode()


def test_an_8bit_body_is_written_as_it_is() -> None:
    part = TextPart("été", "utf-8", "plain", "8bit")

    assert _body(part) == "été\r\n".encode()


def test_set_content_type_parameter() -> None:
    part = (
        TextPart("BEGIN:VCALENDAR", "utf-8", "calendar", "8bit")
        .set_content_type_parameter("method", "REQUEST")
        .set_content_type_parameter("component", "VEVENT")
    )

    assert part.get_media_subtype() == "calendar"
    content_type = part.get_prepared_headers().to_array()[0]
    # Adapted (D1): the parameters read back, in order, instead of upstream's bytes.
    assert content_type.startswith("Content-Type: text/calendar;")
    assert list(decode_parameters(content_type).items()) == [
        ("method", "REQUEST"),
        ("component", "VEVENT"),
        ("charset", "utf-8"),
    ]


def test_set_content_type_parameter_overwrites() -> None:
    part = TextPart("content").set_content_type_parameter("method", "PUBLISH")

    _ = part.set_content_type_parameter("method", "REQUEST")

    content_type = part.get_prepared_headers().to_array()[0]
    assert decode_parameters(content_type)["method"] == "REQUEST"
    assert "PUBLISH" not in content_type


def test_prepared_headers_are_a_copy() -> None:
    part = TextPart("content")

    part.get_prepared_headers().remove("Content-Type")

    assert not part.get_headers().has("Content-Type")
    assert part.get_prepared_headers().has("Content-Type")


def test_headers_added_to_the_part_are_rendered() -> None:
    part = TextPart("content")
    _ = part.get_headers().add_text_header("X-Foo", "bar")

    assert read_part(part)["X-Foo"] == "bar"


def test_to_string_is_the_headers_then_the_body() -> None:
    part = TextPart("content")

    assert part.to_string() == (
        f"{part.get_prepared_headers().to_string()}\r\n{part.body_to_string()}"
    )
    assert part.to_string().encode() == b"".join(part.to_iterable())


def test_a_disposition_and_a_name_are_written() -> None:
    part = TextPart("content").set_disposition("attachment").set_name("notes.txt")

    message = read_part(part)
    assert part.get_disposition() == "attachment"
    assert part.get_name() == "notes.txt"
    assert message.get_param("name") == "notes.txt"
    assert message.get_content_disposition() == "attachment"
    assert message.get_param("name", header="Content-Disposition") == "notes.txt"


def test_a_form_data_part_is_written_in_8bit_without_a_name_in_its_content_type() -> None:
    part = TextPart("content").set_disposition("form-data").set_name("field")

    headers = part.get_prepared_headers()
    assert headers.get_header_body("Content-Transfer-Encoding") == "8bit"
    assert headers.get_header_parameter("Content-Type", "name") == ""


def test_as_debug_string() -> None:
    assert TextPart("content").as_debug_string() == "text/plain charset: utf-8"
    assert (
        TextPart("content", None, "html").set_disposition("inline").as_debug_string()
        == "text/html disposition: inline"
    )
