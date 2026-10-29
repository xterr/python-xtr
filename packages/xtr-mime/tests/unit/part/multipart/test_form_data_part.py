"""multipart/form-data (RFC 7578), the body an HTTP form upload sends.

xtr-mime writes this body itself, not through the mail engine, so its bytes are asserted as
they are. Upstream's serialization cases have no counterpart: a part is not serialized.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.rendered_part import read_part
from tests.support.wire import decode_parameters
from xtr_mime.exception import InvalidArgumentError, RfcComplianceError
from xtr_mime.part import DataPart, TextPart
from xtr_mime.part.multipart import FormDataPart, MixedPart

if TYPE_CHECKING:
    from xtr_mime.part.multipart.form_data_part import FormFields

GIF: Final = Path(__file__).parents[3] / "fixtures" / "mimetypes" / "test.gif"


def _boundary(form: FormDataPart) -> str:
    boundary = form.get_prepared_headers().get_header_parameter("Content-Type", "boundary")
    assert boundary
    return boundary


def _encoding(part: TextPart) -> object:
    return part.get_prepared_headers().get_header_body("Content-Transfer-Encoding")


def _names(form: FormDataPart) -> list[str | None]:
    return [part.get_name() for part in form.get_parts()]


def test_constructor() -> None:
    content = (
        "very very long content that will not be cut even if the length is way more than 76 "
        "characters, ok?"
    )
    text = TextPart("content")
    gif = DataPart.from_path(GIF)

    form = FormDataPart({"foo": content, "bar": text, "baz": gif})

    assert form.get_media_type() == "multipart"
    assert form.get_media_subtype() == "form-data"
    foo, bar, baz = form.get_parts()
    assert [(p.get_name(), p.get_disposition()) for p in (foo, bar, baz)] == [
        ("foo", "form-data"),
        ("bar", "form-data"),
        ("baz", "form-data"),
    ]
    assert foo.get_body() == content
    assert _encoding(foo) == "8bit"
    assert bar.get_body() == "content"
    assert isinstance(baz, DataPart)
    assert baz.get_filename() == "test.gif"
    assert f"\r\n\r\n{content}\r\n--" in form.body_to_string()


def test_nested_array_parts() -> None:
    def p() -> TextPart:
        return TextPart("content", "utf-8", "plain", "8bit")

    fields: FormFields = {
        "foo": p(),
        "bar": {"baz": {0: p(), "qux": p()}},
        "quux": [p(), p()],
        "quuz": {"corge": [p(), p()]},
        "2": p(),
        "0": p(),
        "bar2": {0: {"baz": p()}, "baz": {"qux": p()}},
        3: {"quux2": p()},
        4: {"quux2": [p()]},
        "quuz2": [{"corge": p()}, {"corge": p()}],
        5: {"2": p()},
        6: {"2": p()},
        7: {"0": p()},
        8: {"0": p()},
        9: {"2[0]": p()},
        10: {"2[1]": p()},
        11: {"0[0]": p()},
        12: {"0[1]": p()},
        "qux": [{"foo": p(), "bar": p()}, {"foo": p(), "bar": p()}],
    }

    form = FormDataPart(fields)

    assert _names(form) == [
        "foo",
        "bar[baz][0]",
        "bar[baz][qux]",
        "quux[0]",
        "quux[1]",
        "quuz[corge][0]",
        "quuz[corge][1]",
        "2",
        "0",
        "bar2[0][baz]",
        "bar2[baz][qux]",
        "quux2",
        "quux2[0]",
        "quuz2[0][corge]",
        "quuz2[1][corge]",
        "2",
        "2",
        "0",
        "0",
        "2[0]",
        "2[1]",
        "0[0]",
        "0[1]",
        "qux[0][foo]",
        "qux[0][bar]",
        "qux[1][foo]",
        "qux[1][bar]",
    ]
    assert {part.get_disposition() for part in form.get_parts()} == {"form-data"}


def test_a_list_of_fields_repeats_a_name() -> None:
    form = FormDataPart([{"to": "a@example.com"}, {"to": "b@example.com"}])

    assert _names(form) == ["to", "to"]


def test_exception_on_form_fields_with_integer_keys_and_multiple_values() -> None:
    def p() -> TextPart:
        return TextPart("content", "utf-8", "plain", "8bit")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = FormDataPart([[p(), p()]])

    assert str(caught.value) == (
        "Form field values with integer keys can only have one array element, the key being "
        "the field name and the value being the field value, 2 provided."
    )


def test_exception_on_form_fields_with_disallowed_types_inside_array() -> None:
    fields = cast("FormFields", {"foo": {"bar": "baz", "qux": {"quux": 1}}})

    with pytest.raises(InvalidArgumentError) as caught:
        _ = FormDataPart(fields)

    assert str(caught.value) == (
        'The value of the form field "foo[qux][quux]" can only be a string, a sequence, a '
        'mapping, or an instance of TextPart, "int" given.'
    )


def test_get_parts_throws_on_unexpected_field_type() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = FormDataPart(cast("FormFields", {"foo": object()}))

    assert str(caught.value) == (
        'The value of the form field "foo" can only be a string, a sequence, a mapping, or an '
        'instance of TextPart, "object" given.'
    )


def test_bytes_are_not_a_field_value() -> None:
    with pytest.raises(InvalidArgumentError, match='"bytes" given'):
        _ = FormDataPart(cast("FormFields", {"foo": b"raw"}))


def test_to_string() -> None:
    part = DataPart.from_path(GIF)

    assert base64.b64decode(part.body_to_string()) == GIF.read_bytes()


def test_content_line_length() -> None:
    foo, bar = "foo" * 1000, "bar" * 1000

    form = FormDataPart({"foo": DataPart(foo, "foo.txt", "text/plain"), "bar": bar})

    # Adapted: the form writes the bodies, not the parts, which the mail engine would wrap.
    body = form.body_to_string()
    assert f"\r\n\r\n{foo}\r\n--" in body
    assert f"\r\n\r\n{bar}\r\n--" in body


def test_boundary_content_type_header() -> None:
    form = FormDataPart({"file": DataPart("data.csv", "data.csv", "text/csv")})

    content_type = form.get_prepared_headers().to_array()[0]

    # Adapted (D1): the engine quotes the boundary; it reads back as the eight characters.
    assert content_type.startswith("Content-Type: multipart/form-data;")
    assert re.fullmatch(r"[a-zA-Z0-9\-_]{8}", decode_parameters(content_type)["boundary"])


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
    assert _encoding(part) == "base64"
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
    assert _encoding(part) == "binary"
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
    assert _encoding(field) == "8bit"
    assert part.get_disposition() == "attachment"
    assert _encoding(part) == "base64"


def test_explicit_encoding_beats_the_form_default() -> None:
    form = FormDataPart(
        {
            "explicit": DataPart("Hello World", "explicit.txt", "text/plain", "base64"),
            "default": DataPart("Hello World", "default.txt", "text/plain"),
        }
    )

    explicit, default = form.get_parts()
    assert _encoding(explicit) == "base64"
    assert _encoding(default) == "8bit"


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


def test_a_header_of_the_part_is_written_on_one_line() -> None:
    part = TextPart("value")
    _ = part.get_headers().add_text_header("X-Note", "word " * 30)

    body = FormDataPart({"a": part}).body_to_string()

    assert f"X-Note: {'word ' * 30}\r\n" in body


def test_a_header_with_nothing_to_write_is_left_out() -> None:
    part = TextPart("value")
    _ = part.get_headers().add_text_header("X-Empty", "")

    assert "X-Empty" not in FormDataPart({"a": part}).body_to_string()


def test_the_form_renders_as_its_header_and_body() -> None:
    form = FormDataPart({"a": "b"})

    rendered = b"".join(form.to_iterable())

    assert rendered == (form.get_prepared_headers().to_string() + "\r\n").encode() + b"".join(
        form.body_to_iterable()
    )
    assert form.to_string().encode() == rendered


def test_a_form_nests_in_another_multipart() -> None:
    message = read_part(MixedPart(FormDataPart({"a": "b"})))

    [form] = message.iter_parts()
    [field] = form.iter_parts()
    assert form.get_content_type() == "multipart/form-data"
    assert field.get_param("name", header="Content-Disposition") == "a"
