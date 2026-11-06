"""Images an email's HTML shows by content id: embedded in a related part, references rewritten."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.email_cases import (
    GIF,
    addressed_email,
    assert_clean_error,
    file_part,
    file_stream,
    image_stream,
)
from tests.support.growth import assert_linear_growth
from tests.support.part_shape import shape
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.part import AlternativePart, DataPart, MixedPart, RelatedPart, TextPart

if TYPE_CHECKING:
    from xtr_mime import Email
    from xtr_mime.part import AbstractPart


def _related_body(email: Email) -> tuple[list[AbstractPart], AbstractPart]:
    """Return the related part's parts and the attachment after it, checking the nesting."""
    body = email.get_body()
    assert isinstance(body, MixedPart)
    related, attachment = body.get_parts()
    assert isinstance(related, RelatedPart)
    return list(related.get_parts()), attachment


def test_generate_body_with_an_image_referenced_via_cid() -> None:
    email = addressed_email().html('html content <img src="cid:test.gif">').text("text content")
    _ = email.add_part(DataPart(file_stream())).add_part(DataPart(image_stream(), "test.gif"))

    parts, attachment = _related_body(email)

    assert shape(attachment) == shape(file_part())
    alternative, image = parts
    assert isinstance(alternative, AlternativePart)
    assert isinstance(image, DataPart)
    html = alternative.get_parts()[1]
    assert isinstance(html, TextPart)
    assert f"cid:{image.get_content_id()}" in str(html.get_body())


def test_generate_body_with_an_image_referenced_via_cid_and_content_id() -> None:
    email = addressed_email().text("text content").add_part(DataPart(file_stream()))
    image = DataPart(image_stream(), "test.gif")
    _ = email.add_part(image).html(f'html content <img src="cid:{image.get_content_id()}">')

    parts, attachment = _related_body(email)

    assert shape(attachment) == shape(file_part())
    assert len(parts) == 2
    assert isinstance(parts[0], AlternativePart)


def _html_of_related(email: Email) -> str | bytes:
    body = email.get_body()
    assert isinstance(body, RelatedPart)
    parts = body.get_parts()
    assert len(parts) == 2
    html = parts[0]
    assert isinstance(html, TextPart)
    return html.get_body()


def test_generate_body_with_html_and_inlined_image_twice_referenced_via_cid() -> None:
    image = GIF.read_bytes()
    email = addressed_email().html(io.BytesIO(b'html content <img src="cid:test.gif">'))

    # The same image embedded twice is in the email once.
    _ = email.add_part(DataPart(image, "test.gif").as_inline())
    _ = email.add_part(DataPart(image, "test.gif").as_inline())

    html = _html_of_related(email)
    assert isinstance(html, bytes)
    assert re.fullmatch(rb'html content <img src="cid:[0-9a-f]{32}@xtr">', html)


def test_generate_body_with_html_and_an_image_referenced_as_a_background() -> None:
    email = addressed_email().html('<div background="cid:test.gif"></div>')
    _ = email.add_part(DataPart(GIF.read_bytes(), "test.gif").as_inline())

    html = _html_of_related(email)

    assert re.fullmatch(r'<div background="cid:[0-9a-f]{32}@xtr"></div>', str(html))


def test_generate_body_drops_a_second_part_named_like_a_referenced_one() -> None:
    # Characterises upstream: a part named like one the HTML already shows is left out of the
    # body, whatever it holds — the HTML refers to one part by that name, and it is the first.
    first = DataPart(GIF.read_bytes(), "test.gif").as_inline()
    second = DataPart(b"other content", "test.gif")
    email = addressed_email().html('<img src="cid:test.gif">').add_part(first).add_part(second)

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    assert body.get_parts()[1] is first
    assert len(body.get_parts()) == 2
    assert email.get_attachments() == [first, second]


def test_generate_body_keeps_two_parts_of_one_name_the_html_does_not_show() -> None:
    first = DataPart(b"one", "notes.txt")
    second = DataPart(b"two", "notes.txt")
    email = addressed_email().html('<img src="cid:logo.gif">').add_part(first).add_part(second)

    body = email.get_body()

    assert isinstance(body, MixedPart)
    assert body.get_parts()[1:] == [first, second]


def test_inlined_part_referenced_via_cid_preserves_filename() -> None:
    email = addressed_email().html('html content <img src="cid:logo-image.gif">')
    _ = email.add_part(DataPart(image_stream(), "logo-image.gif").as_inline())

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    inline = body.get_parts()[1]
    assert isinstance(inline, DataPart)
    assert inline.get_name() == "logo-image.gif"
    headers = inline.get_prepared_headers()
    assert headers.get_header_parameter("Content-Type", "name") == "logo-image.gif"
    assert inline.get_disposition() == "inline"


def test_an_inlined_part_without_a_name_is_named_after_its_content_id() -> None:
    image = DataPart(image_stream()).set_content_id("logo@example.com")
    email = addressed_email().html('<img src="cid:logo@example.com">').add_part(image)

    _ = email.get_body()

    assert image.get_name() == "logo@example.com"
    assert image.get_disposition() == "inline"


def _assert_inlined_images_are_referenced_via_their_content_id(email: Email, expected: int) -> None:
    body = email.get_body()
    assert isinstance(body, RelatedPart)
    html_part, *parts = body.get_parts()
    assert len(parts) == expected
    assert isinstance(html_part, TextPart)
    content_ids = [part.get_content_id() for part in parts if isinstance(part, DataPart)]
    html = cast("str", html_part.get_body())
    references = [str(match[1]) for match in re.finditer(r"""cid:([^"'\s>]+)""", html)]
    assert len(references) == expected
    for reference in references:
        assert reference in content_ids, f'"cid:{reference}" does not reference any related part.'
    assert len(set(references)) == expected, "Several references point to the same related part."


def _inline(name: str) -> DataPart:
    return DataPart(image_stream(), name).as_inline()


def test_generate_body_with_inlined_images_whose_cid_names_are_prefixes_of_each_other() -> None:
    html = 'html content <img src="cid:logo"> <img src="cid:logo_2">'
    # "logo" is a strict prefix of "logo_2", the shorter one added first.
    email = addressed_email().html(html).add_part(_inline("logo")).add_part(_inline("logo_2"))
    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)

    # The same pair, the longer one added first.
    email = addressed_email().html(html).add_part(_inline("logo_2")).add_part(_inline("logo"))
    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_with_inlined_images_whose_cid_names_are_nested() -> None:
    html = 'html content <img src="cid:logo"> <img src="cid:logo_2"> <img src="cid:logo_2_3">'
    email = addressed_email().html(html)
    for name in ("logo", "logo_2", "logo_2_3"):
        _ = email.add_part(_inline(name))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 3)


def test_generate_body_with_inlined_images_whose_cid_names_do_not_collide() -> None:
    html = 'html content <img src="cid:one.gif"> <img src="cid:two.gif">'
    email = addressed_email().html(html).add_part(_inline("one.gif")).add_part(_inline("two.gif"))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_with_image_referenced_by_a_content_id_prefixed_by_another_name() -> None:
    email = addressed_email().html(
        'html content <img src="cid:logo"> <img src="cid:logo@example.com">'
    )
    _ = email.add_part(_inline("logo"))
    _ = email.add_part(DataPart(image_stream()).set_content_id("logo@example.com").as_inline())

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_finds_references_whatever_their_case_and_quotes() -> None:
    html = "<IMG SRC=cid:one.gif> <img alt='x' src='cid:two.gif'>"
    email = addressed_email().html(html).add_part(_inline("one.gif")).add_part(_inline("two.gif"))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_rewrites_references_in_an_html_body_given_as_bytes() -> None:
    html = '<img src="cid:test.gif"> café'.encode("iso-8859-1")
    email = addressed_email().html(html, "iso-8859-1")
    _ = email.add_part(_inline("test.gif"))

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    html_part = body.get_parts()[0]
    assert isinstance(html_part, TextPart)
    assert re.fullmatch(
        rb'<img src="cid:[0-9a-f]{32}@xtr"> caf\xe9', cast("bytes", html_part.get_body())
    )


def test_generate_body_refuses_an_html_body_in_an_unknown_charset() -> None:
    email = (
        addressed_email()
        .html(b'<img src="cid:test.gif">', "no-such-charset")
        .add_part(_inline("test.gif"))
    )

    with pytest.raises(
        InvalidArgumentError, match=re.escape("The charset 'no-such-charset' is unknown.")
    ):
        _ = email.get_body()


@pytest.mark.parametrize("run", ["<a ", "<img src=", 'src="cid:'])
def test_a_long_html_body_is_searched_for_references_in_linear_time(run: str) -> None:
    # Each piece opens a tag, or an attribute, that never closes: a search that goes back
    # over the rest of the body from each one takes minutes on a megabyte.
    def render(size: int) -> None:
        email = addressed_email().html(run * (size // len(run))).attach(b"x", "x.txt")
        _ = email.to_string()

    _ = assert_linear_growth(render, 250_000)


@pytest.mark.parametrize(
    ("html", "charset"),
    [
        ('<img src="cid:a.gif">'.encode("utf-16") + b"\x00", "utf-16"),
        ('<img src="cid:a.gif">'.encode("utf-16-le") + b"\xd8", "utf-16-le"),
        (b'<img src="cid:a.gif">', "idna"),
        (b'<img src="cid:a.gif">', "punycode"),
    ],
    ids=["truncated", "unwritable-after-rewrite", "idna", "punycode"],
)
def test_an_html_body_its_charset_cannot_hold_is_refused(html: bytes, charset: str) -> None:
    email = addressed_email().html(html, charset).embed(b"G", "a.gif").attach(b"x", "x.txt")

    with pytest.raises(
        InvalidArgumentError, match=f'^The body is not "{charset}" text: '
    ) as caught:
        _ = email.to_string()

    assert_clean_error(caught.value)
