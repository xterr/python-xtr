"""How a form writes each field: its transfer encoding, its names, and what it refuses."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from tests.support.email_cases import GIF
from tests.support.form_fields import transfer_encoding
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.part import DataPart, TextPart
from xtr_mime.part.multipart import FormDataPart, MixedPart

if TYPE_CHECKING:
    from xtr_mime.part.multipart.form_data_part import FormFields


def _boundary(form: FormDataPart) -> str:
    boundary = form.get_prepared_headers().get_header_parameter("Content-Type", "boundary")
    assert boundary
    return boundary


def test_explicit_encoding_is_kept() -> None:
    form = FormDataPart(
        {
            "file": DataPart("Hello World", "hello.txt", "text/plain", "base64"),
            "text": TextPart("\u00e9t\u00e9", "utf-8", "plain", "quoted-printable"),
            "default": DataPart("Hello World", "default.txt", "text/plain"),
            "field": "value",
        }
    )
    boundary = _boundary(form)
    expected = (
        f"--{boundary}\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Transfer-Encoding: base64\r\n"
        'Content-Disposition: form-data; name="file"; filename="hello.txt"\r\n'
        "\r\n"
        "SGVsbG8gV29ybGQ=\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Transfer-Encoding: quoted-printable\r\n"
        'Content-Disposition: form-data; name="text"\r\n'
        "\r\n"
        "=C3=A9t=C3=A9\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain\r\n"
        "Content-Transfer-Encoding: 8bit\r\n"
        'Content-Disposition: form-data; name="default"; filename="default.txt"\r\n'
        "\r\n"
        "Hello World\r\n"
        f"--{boundary}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Transfer-Encoding: 8bit\r\n"
        'Content-Disposition: form-data; name="field"\r\n'
        "\r\n"
        "value\r\n"
        f"--{boundary}--\r\n"
    )

    assert form.body_to_string() == expected
    # Rendering twice must not change the outcome.
    assert form.body_to_string() == expected
    assert b"".join(form.body_to_iterable()) == expected.encode()


def test_from_path_with_explicit_encoding_is_kept() -> None:
    form = FormDataPart({"file": DataPart.from_path(GIF, None, None, "base64")})

    [part] = form.get_parts()
    assert transfer_encoding(part) == "base64"
    body = b"".join(part.body_to_iterable()).replace(b"\r\n", b"")
    assert body == base64.b64encode(GIF.read_bytes())


def test_a_long_base64_body_is_written_in_lines_of_76() -> None:
    data = bytes(range(256)) * 4
    form = FormDataPart({"file": DataPart(data, "blob.bin", None, "base64")})

    body = form.body_to_string().split("\r\n\r\n", 1)[1].split(f"\r\n--{_boundary(form)}--")[0]

    assert {len(line) for line in body.split("\r\n")[:-1]} == {76}
    assert base64.b64decode(body) == data


def test_binary_encoding_is_kept() -> None:
    form = FormDataPart(
        {"file": DataPart(b"\xff\x00raw", "raw.bin", "application/octet-stream", "binary")}
    )

    [part] = form.get_parts()
    assert transfer_encoding(part) == "binary"
    assert part.body_to_string().encode("utf-8", "surrogateescape") == b"\xff\x00raw"
    assert b"\r\n\r\n\xff\x00raw\r\n--" in b"".join(form.body_to_iterable())


def test_a_binary_body_keeps_its_line_breaks() -> None:
    form = FormDataPart({"file": DataPart(b"a\nb\rc", "raw.bin")})

    assert b"\r\n\r\na\nb\rc\r\n--" in b"".join(form.body_to_iterable())


def test_quoted_printable_data_encodes_its_line_breaks() -> None:
    form = FormDataPart({"file": DataPart(b"a\r\nb", "raw.bin", None, "quoted-printable")})

    assert "\r\n\r\na=0D=0Ab\r\n--" in form.body_to_string()


def test_quoted_printable_text_keeps_its_lines() -> None:
    form = FormDataPart({"text": TextPart("a\nb", "utf-8", "plain", "quoted-printable")})

    assert "\r\n\r\na\r\nb\r\n--" in form.body_to_string()


def test_the_given_part_is_left_as_it_is() -> None:
    part = DataPart("Hello World", "hello.txt", "text/plain")

    [field] = FormDataPart({"file": part}).get_parts()

    # Adapted: upstream turns the given part into a form field; the form works on a copy.
    assert field is not part
    assert transfer_encoding(field) == "8bit"
    assert part.get_disposition() == "attachment"
    assert transfer_encoding(part) == "base64"


def test_explicit_encoding_beats_the_form_default() -> None:
    form = FormDataPart(
        {
            "explicit": DataPart("Hello World", "explicit.txt", "text/plain", "base64"),
            "default": DataPart("Hello World", "default.txt", "text/plain"),
        }
    )

    explicit, default = form.get_parts()
    assert transfer_encoding(explicit) == "base64"
    assert transfer_encoding(default) == "8bit"


def test_names_are_raw_utf8_with_quotes_and_line_breaks_escaped() -> None:
    form = FormDataPart({"déjà": DataPart("x", 'déjà%"\n\r.txt', "text/plain")})

    body = b"".join(form.body_to_iterable())

    # Was ParameterizedHeaderTest::testFormDataUtf8: HTTP takes the name raw, as browsers do.
    assert (
        'Content-Disposition: form-data; name="déjà"; filename="déjà%%22%0A%0D.txt"\r\n'.encode()
        in body
    )


def test_a_field_value_is_written_in_utf8() -> None:
    form = FormDataPart({"city": "Zürich"})

    assert "\r\n\r\nZürich\r\n--".encode() in b"".join(form.body_to_iterable())


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"a\x00b": "value"}, id="nul in a name"),
        pytest.param(
            {"a": TextPart("v").set_content_type_parameter("x", "1\r\nX-Injected: 1")},
            id="line break in a content type parameter",
        ),
    ],
)
def test_a_header_injection_is_refused(fields: FormFields) -> None:
    form = FormDataPart(fields)

    with pytest.raises(RfcComplianceError, match="must not contain"):
        _ = form.body_to_string()


def test_a_value_utf8_cannot_hold_is_refused() -> None:
    form = FormDataPart({"f": "\ud800"})

    with pytest.raises(InvalidArgumentError, match='not "utf-8"') as caught:
        _ = b"".join(form.to_iterable())

    assert caught.type is InvalidArgumentError
    # The message is written out as it is, so it must not carry what UTF-8 cannot hold.
    assert "\ud800" not in str(caught.value)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"\ud800": "v"}, id="field name"),
        pytest.param({"f": DataPart(b"x", "\ud800.txt")}, id="filename"),
    ],
)
def test_a_name_utf8_cannot_hold_is_refused(fields: FormFields) -> None:
    form = FormDataPart(fields)

    with pytest.raises(RfcComplianceError, match="cannot be written in UTF-8") as caught:
        _ = form.body_to_string()

    assert "\ud800" not in str(caught.value)


def test_a_body_its_charset_cannot_hold_is_refused() -> None:
    form = FormDataPart({"f": TextPart("日本", "iso-8859-1")})

    with pytest.raises(InvalidArgumentError, match='not "iso-8859-1"') as caught:
        _ = form.body_to_string()

    assert caught.type is InvalidArgumentError


def test_a_body_in_an_unknown_charset_is_refused() -> None:
    form = FormDataPart({"f": TextPart("x", "x-unknown")})

    with pytest.raises(InvalidArgumentError, match='not "x-unknown"') as caught:
        _ = form.body_to_string()

    assert caught.type is InvalidArgumentError


def test_a_form_that_cannot_be_written_is_refused_inside_another_multipart() -> None:
    mixed = MixedPart(TextPart("x"), FormDataPart({"f": "\ud800"}))

    with pytest.raises(InvalidArgumentError, match='not "utf-8"') as caught:
        _ = mixed.to_string()

    assert caught.type is InvalidArgumentError


def test_a_header_of_the_part_is_written_on_one_line() -> None:
    part = TextPart("value")
    _ = part.get_headers().add_text_header("X-Note", "word " * 30)

    body = FormDataPart({"a": part}).body_to_string()

    assert f"X-Note: {'word ' * 30}\r\n" in body


def test_a_header_with_nothing_to_write_is_left_out() -> None:
    part = TextPart("value")
    _ = part.get_headers().add_text_header("X-Empty", "")

    assert "X-Empty" not in FormDataPart({"a": part}).body_to_string()
