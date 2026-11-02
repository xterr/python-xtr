"""multipart/form-data (RFC 7578), the body an HTTP form upload sends.

xtr-mime writes this body itself, not through the mail engine, so its bytes are asserted as
they are. Upstream's serialization cases have no counterpart: a part is not serialized. How
each field's body and headers are written is tested in ``test_form_data_part_body.py``.
"""

from __future__ import annotations

import base64
import re
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.email_cases import GIF
from tests.support.form_fields import transfer_encoding
from tests.support.rendered_part import read_part
from tests.support.wire import decode_parameters
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.part import DataPart, TextPart
from xtr_mime.part.multipart import FormDataPart, MixedPart

if TYPE_CHECKING:
    from xtr_mime.part.multipart.form_data_part import FormFields


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
    assert transfer_encoding(foo) == "8bit"
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
