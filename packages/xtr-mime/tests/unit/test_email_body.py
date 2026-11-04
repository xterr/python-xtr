"""The body an email builds from its text, its HTML and its attachments, and what it takes."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.email_cases import (
    GIF,
    NO_BODY,
    TEST,
    addressed_email,
    file_part,
    file_stream,
    html_part,
    image_part,
    image_stream,
    text_part,
)
from tests.support.part_shape import shape
from xtr_mime import Email
from xtr_mime.exception import LogicError
from xtr_mime.part import AlternativePart, DataPart, File, MixedPart, TextPart

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def test_generate_body_throws_when_empty_body() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_BODY)}$"):
        _ = Email().get_body()


def test_get_body() -> None:
    text = TextPart("text content")

    email = Email().set_body(text)

    assert email.get_body() is text


def test_generate_body_with_text_only() -> None:
    email = addressed_email().text("text content")

    assert shape(email.get_body()) == shape(text_part())
    assert email.get_text_body() == "text content"


def test_generate_body_with_html_only() -> None:
    email = addressed_email().html("html content")

    assert shape(email.get_body()) == shape(html_part())
    assert email.get_html_body() == "html content"


def test_generate_body_with_text_and_html() -> None:
    email = addressed_email().html("html content").text("text content")

    assert shape(email.get_body()) == shape(AlternativePart(text_part(), html_part()))


def test_generate_body_with_text_and_html_not_utf8() -> None:
    email = addressed_email().html("html content", "iso-8859-1").text("text content", "iso-8859-1")

    assert email.get_text_charset() == "iso-8859-1"
    assert email.get_html_charset() == "iso-8859-1"
    expected = AlternativePart(
        TextPart("text content", "iso-8859-1"), TextPart("html content", "iso-8859-1", "html")
    )
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_content_and_attached_file() -> None:
    email = addressed_email().add_part(DataPart(file_stream())).text("text content")

    assert shape(email.get_body()) == shape(MixedPart(text_part(), file_part()))


def test_generate_body_with_html_content_and_attached_file() -> None:
    email = addressed_email().add_part(DataPart(file_stream())).html("html content")

    assert shape(email.get_body()) == shape(MixedPart(html_part(), file_part()))


def test_generate_body_with_html_content_and_inline_image_not_referenced() -> None:
    email = addressed_email().add_part(DataPart(image_stream()).as_inline()).html("html content")

    expected = MixedPart(html_part(), DataPart(image_stream()).as_inline())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_attached_file_only() -> None:
    email = addressed_email().add_part(DataPart(file_stream()))

    assert shape(email.get_body()) == shape(MixedPart(file_part()))


def test_generate_body_with_inline_image_only() -> None:
    email = addressed_email().add_part(DataPart(image_stream()).as_inline())

    assert shape(email.get_body()) == shape(MixedPart(DataPart(image_stream()).as_inline()))


def test_generate_body_with_text_and_html_content_and_attached_file() -> None:
    email = addressed_email().html("html content").text("text content")
    _ = email.add_part(DataPart(file_stream()))

    expected = MixedPart(AlternativePart(text_part(), html_part()), file_part())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_and_html_and_attached_file_and_image_not_referenced() -> None:
    email = addressed_email().html("html content").text("text content")
    _ = email.add_part(DataPart(file_stream())).add_part(DataPart(image_stream(), "test.gif"))

    expected = MixedPart(AlternativePart(text_part(), html_part()), file_part(), image_part())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_and_attached_file_and_image_not_referenced() -> None:
    email = addressed_email().text("text content")
    _ = email.add_part(DataPart(file_stream())).add_part(DataPart(image_stream(), "test.gif"))

    expected = MixedPart(text_part(), file_part(), image_part())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_an_image_not_referenced_via_cid() -> None:
    content = 'html content <img src="test.gif">'
    email = addressed_email().html(content).text("text content")
    _ = email.add_part(DataPart(file_stream())).add_part(DataPart(image_stream(), "test.gif"))

    full_html = TextPart(content, "utf-8", "html")
    expected = MixedPart(AlternativePart(text_part(), full_html), file_part(), image_part())
    assert shape(email.get_body()) == shape(expected)


def test_attachments() -> None:
    contents = TEST.read_bytes()
    attached = DataPart(file_stream(), "test")
    inline = DataPart(contents, "test").as_inline()

    email = (
        Email()
        .add_part(DataPart(file_stream(), "test"))
        .add_part(DataPart(contents, "test").as_inline())
    )

    assert [shape(part) for part in email.get_attachments()] == [shape(attached), shape(inline)]


def test_attachments_from_a_path() -> None:
    attached = DataPart.from_path(TEST, "test")
    inline = DataPart.from_path(TEST, "test").as_inline()

    email = Email().add_part(DataPart(File(TEST))).add_part(DataPart(File(TEST)).as_inline())

    bodies = [part.body_to_string() for part in email.get_attachments()]
    assert bodies == [attached.body_to_string(), inline.body_to_string()]
    headers = [part.get_prepared_headers().to_array() for part in email.get_attachments()]
    assert headers == [
        attached.get_prepared_headers().to_array(),
        inline.get_prepared_headers().to_array(),
    ]


def test_attach_and_embed_build_data_parts() -> None:
    email = (
        Email()
        .attach(b"data", "data.bin", "application/x-test")
        .embed(b"gif", "logo.gif", "image/gif")
    )
    _ = email.attach_from_path(TEST, "named").embed_from_path(GIF)

    attached, embedded, from_path, embedded_from_path = email.get_attachments()
    assert (attached.get_filename(), attached.get_content_type()) == (
        "data.bin",
        "application/x-test",
    )
    assert attached.get_disposition() == "attachment"
    assert (embedded.get_filename(), embedded.get_disposition()) == ("logo.gif", "inline")
    assert from_path.get_filename() == "named"
    assert from_path.get_body() == TEST.read_bytes()
    assert (embedded_from_path.get_filename(), embedded_from_path.get_content_type()) == (
        "test.gif",
        "image/gif",
    )
    assert embedded_from_path.get_disposition() == "inline"


def test_an_attachment_from_a_path_is_read_when_the_email_is_rendered(tmp_path: Path) -> None:
    path = tmp_path / "late.txt"
    _ = path.write_bytes(b"before")
    email = Email().attach_from_path(path)

    _ = path.write_bytes(b"foo_bar_xyz_123")

    assert email.get_attachments()[0].get_body() == b"foo_bar_xyz_123"


def test_html_body_expect_string_bytes_file_or_none() -> None:
    with pytest.raises(
        TypeError,
        match=r'^The body must be a string, bytes, a binary file or None \(got "bool"\)\.$',
    ):
        _ = Email().html(cast("str", cast("object", False)))


def test_html_body_accepted_types() -> None:
    email = Email()

    assert email.html("foo").get_html_body() == "foo"
    assert email.html(None).get_html_body() is None
    contents = TEST.read_bytes()
    assert email.html(contents).get_html_body() == contents
    handle = io.BytesIO(contents)
    assert email.html(handle).get_html_body() is handle


def test_text_body_expect_string_bytes_file_or_none() -> None:
    with pytest.raises(
        TypeError,
        match=r'^The body must be a string, bytes, a binary file or None \(got "bool"\)\.$',
    ):
        _ = Email().text(cast("str", cast("object", False)))


def test_text_body_accepted_types() -> None:
    email = Email()

    assert email.text("foo").get_text_body() == "foo"
    assert email.text(None).get_text_body() is None
    contents = TEST.read_bytes()
    assert email.text(contents).get_text_body() == contents


def test_body_cache() -> None:
    email = Email().from_("fabien@example.com").to("fabien@example.com").text("foo")

    # The same body object each time, so a signature hashes the same boundaries.
    assert email.get_body() is email.get_body()


BODY_CHANGES: Final[list[Callable[[Email], Email]]] = [
    lambda email: email.html("<b>bar</b>"),
    lambda email: email.text("bar"),
    lambda email: email.add_part(DataPart(b"bar")),
]


@pytest.mark.parametrize("change", BODY_CHANGES, ids=["html", "text", "part"])
def test_a_change_to_the_body_resets_the_cache(change: Callable[[Email], Email]) -> None:
    email = Email().from_("fabien@example.com").to("fabien@example.com").text("foo")
    first = email.get_body()

    _ = change(email)

    assert email.get_body() is not first
