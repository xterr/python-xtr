"""An email: the builder of addresses, subject, priority, bodies and attachments.

Upstream's serialization cases (``serialize``, the serializer's normalizers, the unserialize
guards on the charsets, the attachment body kept in or out of the payload) have no counterpart:
a queued email travels through xtr-mailer's codec, which carries an attachment from a path as
the path. Its case for the header assertion of the test constraints belongs to the testing
assertions. Upstream compares parts with object equality; parts have none here (a multipart's
boundary is random), so a tree is compared by its shape.
"""

from __future__ import annotations

import io
import re
import time
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.part_shape import shape
from xtr_mime import Address, Email, Group
from xtr_mime.exception import InvalidArgumentError, LogicError, MimeError
from xtr_mime.header import MailboxListHeader
from xtr_mime.part import (
    AlternativePart,
    DataPart,
    File,
    MixedPart,
    RelatedPart,
    TextPart,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from email.message import EmailMessage

    from xtr_mime.part import AbstractPart

FIXTURES: Final = Path(__file__).parents[1] / "fixtures"
TEST: Final = FIXTURES / "mimetypes" / "test"
GIF: Final = FIXTURES / "mimetypes" / "test.gif"
CONTENT: Final = FIXTURES / "content.txt"
NO_BODY: Final = "A message must have a text or an HTML part or attachments."


def _email() -> Email:
    return Email().from_("me@example.com").to("you@example.com")


def _file() -> io.BytesIO:
    return io.BytesIO(TEST.read_bytes())


def _image() -> io.BytesIO:
    return io.BytesIO(GIF.read_bytes())


def _text() -> TextPart:
    return TextPart("text content")


def _html() -> TextPart:
    return TextPart("html content", "utf-8", "html")


def _file_part() -> DataPart:
    return DataPart(_file())


def _image_part() -> DataPart:
    return DataPart(_image(), "test.gif")


def test_subject() -> None:
    email = Email().subject("Subject")

    assert email.get_subject() == "Subject"


def test_date() -> None:
    date = datetime.now(UTC)

    email = Email().date(date)

    assert email.get_date() == date


def test_return_path() -> None:
    email = Email().return_path("fabien@example.com")

    assert email.get_return_path() == Address("fabien@example.com")


def test_sender() -> None:
    email = Email().sender("fabien@example.com")
    assert email.get_sender() == Address("fabien@example.com")

    fabien = Address("fabien@example.com")
    _ = email.sender(fabien)
    assert email.get_sender() is fabien


def test_from_with_no_address() -> None:
    with pytest.raises(
        LogicError, match=r'^"from_\(\)" must be called with at least one address\.$'
    ):
        _ = Email().from_()


def _set(email: Email, kind: str, *addresses: Address | str) -> Email:
    setters: dict[str, Callable[..., Email]] = {
        "from": email.from_,
        "reply_to": email.reply_to,
        "to": email.to,
        "cc": email.cc,
        "bcc": email.bcc,
    }
    return setters[kind](*addresses)


def _add(email: Email, kind: str, *addresses: Address | str) -> Email:
    adders: dict[str, Callable[..., Email]] = {
        "from": email.add_from,
        "reply_to": email.add_reply_to,
        "to": email.add_to,
        "cc": email.add_cc,
        "bcc": email.add_bcc,
    }
    return adders[kind](*addresses)


def _get(email: Email, kind: str) -> list[Address]:
    getters: dict[str, Callable[[], list[Address]]] = {
        "from": email.get_from,
        "reply_to": email.get_reply_to,
        "to": email.get_to,
        "cc": email.get_cc,
        "bcc": email.get_bcc,
    }
    return getters[kind]()


ADDRESS_LISTS: Final = ["from", "reply_to", "to", "cc", "bcc"]


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_an_address_list_is_set_then_added_to(kind: str) -> None:
    email = Email()
    helene = Address("helene@example.com")
    thomas = Address("thomas@example.com", "Thomas")
    caramel = Address("caramel@example.com")

    assert _set(email, kind, "fabien@example.com", helene, thomas) is email
    assert _get(email, kind) == [Address("fabien@example.com"), helene, thomas]
    assert _get(email, kind)[1] is helene

    assert _add(email, kind, "lucas@example.com", caramel) is email
    got = _get(email, kind)
    assert got == [
        Address("fabien@example.com"),
        helene,
        thomas,
        Address("lucas@example.com"),
        caramel,
    ]
    assert got[4] is caramel


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_adding_to_an_address_list_not_set_creates_it(kind: str) -> None:
    email = _add(Email(), kind, "lucas@example.com", Address("caramel@example.com"))

    assert len(_get(email, kind)) == 2


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_setting_an_address_list_again_replaces_it(kind: str) -> None:
    caramel = Address("caramel@example.com")
    email = _set(Email(), kind, "lucas@example.com")

    _ = _set(email, kind, caramel)

    assert _get(email, kind) == [caramel]


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_an_address_list_not_set_is_empty(kind: str) -> None:
    assert _get(Email(), kind) == []


def test_to_with_an_empty_group() -> None:
    email = Email().from_("fabien@example.com").bcc("helene@example.com").text("content")
    group = Group("undisclosed-recipients")
    _ = email.get_headers().add_mailbox_list_header("To", [group])

    assert email.get_to() == []
    to = email.get_headers().get("To")
    assert isinstance(to, MailboxListHeader)
    assert to.get_address_list() == [group]
    assert to.to_string() == "To: undisclosed-recipients:;"
    email.ensure_validity()


def test_get_to_flattens_the_groups() -> None:
    email = Email().from_("fabien@example.com")
    chair = Address("chair@example.com")
    observer = Address("observer@example.com")
    _ = email.get_headers().add_mailbox_list_header("To", [Group("Board", [chair]), observer])

    assert email.get_to() == [chair, observer]
    to = email.get_headers().get("To")
    assert to is not None
    assert to.to_string() == "To: Board: chair@example.com;, observer@example.com"


def test_priority() -> None:
    email = Email()
    assert email.get_priority() == 3

    _ = email.priority(1)
    assert email.get_priority() == 1
    _ = email.priority(10)
    assert email.get_priority() == 5
    _ = email.priority(-10)
    assert email.get_priority() == 1


@pytest.mark.parametrize("value", ["12 (High)", "1" * 4301], ids=["two-digits", "many-digits"])
def test_a_priority_header_of_several_digits_reads_as_the_lowest(value: str) -> None:
    # Two digits from 1 to 5 make 11 or more: brought between 1 and 5, as priority() does.
    email = Email()
    _ = email.get_headers().add_text_header("X-Priority", value)

    assert email.get_priority() == 5


def test_priority_is_written_with_its_label() -> None:
    email = Email().priority(Email.PRIORITY_NORMAL)

    assert email.get_headers().get_header_body("X-Priority") == "3 (Normal)"


def test_priority_reads_the_leading_digits_of_the_header() -> None:
    email = Email()
    _ = email.get_headers().add_text_header("X-Priority", "2 (High)")

    assert email.get_priority() == 2


def test_generate_body_throws_when_empty_body() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_BODY)}$"):
        _ = Email().get_body()


def test_get_body() -> None:
    text = TextPart("text content")

    email = Email().set_body(text)

    assert email.get_body() is text


def test_generate_body_with_text_only() -> None:
    email = _email().text("text content")

    assert shape(email.get_body()) == shape(_text())
    assert email.get_text_body() == "text content"


def test_generate_body_with_html_only() -> None:
    email = _email().html("html content")

    assert shape(email.get_body()) == shape(_html())
    assert email.get_html_body() == "html content"


def test_generate_body_with_text_and_html() -> None:
    email = _email().html("html content").text("text content")

    assert shape(email.get_body()) == shape(AlternativePart(_text(), _html()))


def test_generate_body_with_text_and_html_not_utf8() -> None:
    email = _email().html("html content", "iso-8859-1").text("text content", "iso-8859-1")

    assert email.get_text_charset() == "iso-8859-1"
    assert email.get_html_charset() == "iso-8859-1"
    expected = AlternativePart(
        TextPart("text content", "iso-8859-1"), TextPart("html content", "iso-8859-1", "html")
    )
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_content_and_attached_file() -> None:
    email = _email().add_part(DataPart(_file())).text("text content")

    assert shape(email.get_body()) == shape(MixedPart(_text(), _file_part()))


def test_generate_body_with_html_content_and_attached_file() -> None:
    email = _email().add_part(DataPart(_file())).html("html content")

    assert shape(email.get_body()) == shape(MixedPart(_html(), _file_part()))


def test_generate_body_with_html_content_and_inline_image_not_referenced() -> None:
    email = _email().add_part(DataPart(_image()).as_inline()).html("html content")

    assert shape(email.get_body()) == shape(MixedPart(_html(), DataPart(_image()).as_inline()))


def test_generate_body_with_attached_file_only() -> None:
    email = _email().add_part(DataPart(_file()))

    assert shape(email.get_body()) == shape(MixedPart(_file_part()))


def test_generate_body_with_inline_image_only() -> None:
    email = _email().add_part(DataPart(_image()).as_inline())

    assert shape(email.get_body()) == shape(MixedPart(DataPart(_image()).as_inline()))


def test_generate_body_with_text_and_html_content_and_attached_file() -> None:
    email = _email().html("html content").text("text content").add_part(DataPart(_file()))

    expected = MixedPart(AlternativePart(_text(), _html()), _file_part())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_and_html_and_attached_file_and_image_not_referenced() -> None:
    email = _email().html("html content").text("text content")
    _ = email.add_part(DataPart(_file())).add_part(DataPart(_image(), "test.gif"))

    expected = MixedPart(AlternativePart(_text(), _html()), _file_part(), _image_part())
    assert shape(email.get_body()) == shape(expected)


def test_generate_body_with_text_and_attached_file_and_image_not_referenced() -> None:
    email = _email().text("text content")
    _ = email.add_part(DataPart(_file())).add_part(DataPart(_image(), "test.gif"))

    assert shape(email.get_body()) == shape(MixedPart(_text(), _file_part(), _image_part()))


def test_generate_body_with_an_image_not_referenced_via_cid() -> None:
    content = 'html content <img src="test.gif">'
    email = _email().html(content).text("text content")
    _ = email.add_part(DataPart(_file())).add_part(DataPart(_image(), "test.gif"))

    full_html = TextPart(content, "utf-8", "html")
    expected = MixedPart(AlternativePart(_text(), full_html), _file_part(), _image_part())
    assert shape(email.get_body()) == shape(expected)


def _related_body(email: Email) -> tuple[list[AbstractPart], AbstractPart]:
    """Return the related part's parts and the attachment after it, checking the nesting."""
    body = email.get_body()
    assert isinstance(body, MixedPart)
    related, attachment = body.get_parts()
    assert isinstance(related, RelatedPart)
    return list(related.get_parts()), attachment


def test_generate_body_with_an_image_referenced_via_cid() -> None:
    email = _email().html('html content <img src="cid:test.gif">').text("text content")
    _ = email.add_part(DataPart(_file())).add_part(DataPart(_image(), "test.gif"))

    parts, attachment = _related_body(email)

    assert shape(attachment) == shape(_file_part())
    alternative, image = parts
    assert isinstance(alternative, AlternativePart)
    assert isinstance(image, DataPart)
    html = alternative.get_parts()[1]
    assert isinstance(html, TextPart)
    assert f"cid:{image.get_content_id()}" in str(html.get_body())


def test_generate_body_with_an_image_referenced_via_cid_and_content_id() -> None:
    email = _email().text("text content").add_part(DataPart(_file()))
    image = DataPart(_image(), "test.gif")
    _ = email.add_part(image).html(f'html content <img src="cid:{image.get_content_id()}">')

    parts, attachment = _related_body(email)

    assert shape(attachment) == shape(_file_part())
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
    email = _email().html(io.BytesIO(b'html content <img src="cid:test.gif">'))

    # The same image embedded twice is in the email once.
    _ = email.add_part(DataPart(image, "test.gif").as_inline())
    _ = email.add_part(DataPart(image, "test.gif").as_inline())

    html = _html_of_related(email)
    assert isinstance(html, bytes)
    assert re.fullmatch(rb'html content <img src="cid:[0-9a-f]{32}@xtr">', html)


def test_generate_body_with_html_and_an_image_referenced_as_a_background() -> None:
    email = _email().html('<div background="cid:test.gif"></div>')
    _ = email.add_part(DataPart(GIF.read_bytes(), "test.gif").as_inline())

    html = _html_of_related(email)

    assert re.fullmatch(r'<div background="cid:[0-9a-f]{32}@xtr"></div>', str(html))


def test_generate_body_drops_a_second_part_named_like_a_referenced_one() -> None:
    # Characterises upstream: a part named like one the HTML already shows is left out of the
    # body, whatever it holds — the HTML refers to one part by that name, and it is the first.
    first = DataPart(GIF.read_bytes(), "test.gif").as_inline()
    second = DataPart(b"other content", "test.gif")
    email = _email().html('<img src="cid:test.gif">').add_part(first).add_part(second)

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    assert body.get_parts()[1] is first
    assert len(body.get_parts()) == 2
    assert email.get_attachments() == [first, second]


def test_generate_body_keeps_two_parts_of_one_name_the_html_does_not_show() -> None:
    first = DataPart(b"one", "notes.txt")
    second = DataPart(b"two", "notes.txt")
    email = _email().html('<img src="cid:logo.gif">').add_part(first).add_part(second)

    body = email.get_body()

    assert isinstance(body, MixedPart)
    assert body.get_parts()[1:] == [first, second]


def test_inlined_part_referenced_via_cid_preserves_filename() -> None:
    email = _email().html('html content <img src="cid:logo-image.gif">')
    _ = email.add_part(DataPart(_image(), "logo-image.gif").as_inline())

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    inline = body.get_parts()[1]
    assert isinstance(inline, DataPart)
    assert inline.get_name() == "logo-image.gif"
    headers = inline.get_prepared_headers()
    assert headers.get_header_parameter("Content-Type", "name") == "logo-image.gif"
    assert inline.get_disposition() == "inline"


def test_an_inlined_part_without_a_name_is_named_after_its_content_id() -> None:
    image = DataPart(_image()).set_content_id("logo@example.com")
    email = _email().html('<img src="cid:logo@example.com">').add_part(image)

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
    return DataPart(_image(), name).as_inline()


def test_generate_body_with_inlined_images_whose_cid_names_are_prefixes_of_each_other() -> None:
    html = 'html content <img src="cid:logo"> <img src="cid:logo_2">'
    # "logo" is a strict prefix of "logo_2", the shorter one added first.
    email = _email().html(html).add_part(_inline("logo")).add_part(_inline("logo_2"))
    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)

    # The same pair, the longer one added first.
    email = _email().html(html).add_part(_inline("logo_2")).add_part(_inline("logo"))
    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_with_inlined_images_whose_cid_names_are_nested() -> None:
    html = 'html content <img src="cid:logo"> <img src="cid:logo_2"> <img src="cid:logo_2_3">'
    email = _email().html(html)
    for name in ("logo", "logo_2", "logo_2_3"):
        _ = email.add_part(_inline(name))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 3)


def test_generate_body_with_inlined_images_whose_cid_names_do_not_collide() -> None:
    html = 'html content <img src="cid:one.gif"> <img src="cid:two.gif">'
    email = _email().html(html).add_part(_inline("one.gif")).add_part(_inline("two.gif"))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_with_image_referenced_by_a_content_id_prefixed_by_another_name() -> None:
    email = _email().html('html content <img src="cid:logo"> <img src="cid:logo@example.com">')
    _ = email.add_part(_inline("logo"))
    _ = email.add_part(DataPart(_image()).set_content_id("logo@example.com").as_inline())

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_finds_references_whatever_their_case_and_quotes() -> None:
    html = "<IMG SRC=cid:one.gif> <img alt='x' src='cid:two.gif'>"
    email = _email().html(html).add_part(_inline("one.gif")).add_part(_inline("two.gif"))

    _assert_inlined_images_are_referenced_via_their_content_id(email, 2)


def test_generate_body_rewrites_references_in_an_html_body_given_as_bytes() -> None:
    email = _email().html('<img src="cid:test.gif"> café'.encode("iso-8859-1"), "iso-8859-1")
    _ = email.add_part(_inline("test.gif"))

    body = email.get_body()

    assert isinstance(body, RelatedPart)
    html = body.get_parts()[0]
    assert isinstance(html, TextPart)
    assert re.fullmatch(
        rb'<img src="cid:[0-9a-f]{32}@xtr"> caf\xe9', cast("bytes", html.get_body())
    )


def test_generate_body_refuses_an_html_body_in_an_unknown_charset() -> None:
    email = (
        _email().html(b'<img src="cid:test.gif">', "no-such-charset").add_part(_inline("test.gif"))
    )

    with pytest.raises(
        InvalidArgumentError, match=re.escape("The charset 'no-such-charset' is unknown.")
    ):
        _ = email.get_body()


@pytest.mark.parametrize("run", ["<a ", "<img src=", 'src="cid:'])
def test_a_long_html_body_is_searched_for_references_in_linear_time(run: str) -> None:
    # Each piece opens a tag, or an attribute, that never closes: a search that goes back
    # over the rest of the body from each one takes minutes on a megabyte.
    email = _email().html(run * (1_000_000 // len(run))).attach(b"x", "x.txt")
    started = time.perf_counter()

    _ = email.to_string()

    assert time.perf_counter() - started < 1


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
    email = _email().html(html, charset).embed(b"G", "a.gif").attach(b"x", "x.txt")

    with pytest.raises(
        InvalidArgumentError, match=f'^The body is not "{charset}" text: '
    ) as caught:
        _ = email.to_string()

    _assert_clean_error(caught.value)


def test_attachments() -> None:
    contents = TEST.read_bytes()
    attached = DataPart(_file(), "test")
    inline = DataPart(contents, "test").as_inline()

    email = (
        Email().add_part(DataPart(_file(), "test")).add_part(DataPart(contents, "test").as_inline())
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


def test_invalid_body_with_empty_email() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_BODY)}$"):
        Email().ensure_validity()


def _valid_recipients() -> Email:
    return Email().to("test@example.com").from_("test@example.com")


def test_body_with_text_is_valid() -> None:
    _valid_recipients().text("foo").ensure_validity()


def test_body_with_html_is_valid() -> None:
    _valid_recipients().html("foo").ensure_validity()


def test_empty_body_with_attachments_is_valid() -> None:
    _valid_recipients().add_part(DataPart("foo")).ensure_validity()


def test_set_body_is_valid() -> None:
    _valid_recipients().set_body(TextPart("foo")).ensure_validity()


def test_an_email_marked_as_unsent_is_not_valid() -> None:
    email = _valid_recipients().text("foo")
    _ = email.get_headers().add_text_header("X-Unsent", "1")

    with pytest.raises(LogicError, match=re.escape('Cannot send messages marked as "draft".')):
        email.ensure_validity()


def test_a_copy_has_attachments_of_its_own() -> None:
    email = _email().text("foo")

    copied = email.__copy__()
    _ = copied.add_part(DataPart(b"bar")).subject("Copy")

    assert email.get_attachments() == []
    assert not email.get_headers().has("Subject")


def test_to_string_renders_text_html_an_attachment_and_an_inline_image() -> None:
    email = _email().subject("Hello").text("text content")
    _ = email.html('<p>html</p><img src="cid:logo.gif">').embed(
        GIF.read_bytes(), "logo.gif", "image/gif"
    )
    _ = email.attach(b"report", "report.txt", "text/plain")

    parsed = BytesParser(policy=policy.default).parsebytes(b"".join(email.to_iterable()))

    assert parsed["Subject"] == "Hello"
    assert [part.get_content_type() for part in parsed.walk()] == [
        "multipart/mixed",
        "multipart/related",
        "multipart/alternative",
        "text/plain",
        "text/html",
        "image/gif",
        "text/plain",
    ]
    image = next(part for part in parsed.walk() if part.get_content_type() == "image/gif")
    html = next(part for part in parsed.walk() if part.get_content_type() == "text/html")
    content_id = str(cast("object", image["Content-ID"])).strip("<>")
    assert f'src="cid:{content_id}"'.encode() in _decoded(html)
    assert _decoded(image) == GIF.read_bytes()


def _decoded(part: EmailMessage) -> bytes:
    return cast("bytes", part.get_payload(decode=True))


# Hostile input: whatever a setter is handed, a message is either refused with one of this
# package's errors, its text free of what was handed raw, or written without a header of its own.

INJECTED: Final = "x@example.com\r\nBcc: victim@example.com"


def _assert_clean_error(error: BaseException) -> None:
    text = str(error)
    assert not re.search(r"[\x00-\x1f\x7f\u2028\u2029]", text), text
    _ = text.encode("utf-8")  # no lone surrogate


def _render_or_refuse(email: Email) -> bytes | None:
    """Render ``email``; return ``None`` when it is refused, checking the error is clean."""
    try:
        return b"".join(email.to_iterable())
    except MimeError as error:
        _assert_clean_error(error)
        return None


def _headers_of(rendered: bytes) -> list[str]:
    head = rendered.partition(b"\r\n\r\n")[0].decode("utf-8", "surrogateescape")
    return [
        line.partition(":")[0] for line in head.split("\r\n") if not line.startswith((" ", "\t"))
    ]


def _addresses_of(rendered: bytes) -> list[str]:
    """Return every address a reader finds in the address headers of ``rendered``."""
    parsed = BytesParser(policy=policy.default).parsebytes(rendered)
    names = ("From", "Sender", "Reply-To", "To", "Cc", "Bcc", "Return-Path")
    values = [str(cast("object", parsed[name])) for name in names if name in parsed]
    return [address for _, address in getaddresses(values)]


HOSTILE_VALUES: Final[list[tuple[str, Callable[[Email], Email]]]] = [
    ("subject-crlf", lambda email: email.subject("Hi\r\nBcc: victim@example.com")),
    ("subject-lf", lambda email: email.subject("Hi\nBcc: victim@example.com")),
    ("subject-nul", lambda email: email.subject("Hi\x00there")),
    ("subject-surrogate", lambda email: email.subject("Hi \udce9")),
    ("subject-encoded-crlf", lambda email: email.subject("=?utf-8?q?=0D=0ABcc:_v@example.com?=")),
    ("subject-overlong-word", lambda email: email.subject("x" * 1000)),
    ("attach-name", lambda email: email.attach(b"x", "evil\r\nBcc: victim@example.com.txt")),
    (
        "attach-content-type",
        lambda email: email.attach(b"x", "evil.txt", "text/plain\r\nBcc: victim@example.com"),
    ),
    ("embed-name-nul", lambda email: email.embed(b"x", "evil\x00.gif")),
    ("attach-name-surrogate", lambda email: email.attach(b"x", "evil\udce9.txt")),
    ("text-surrogate", lambda email: email.text("caf\udce9")),
    ("html-surrogate", lambda email: email.html("caf\udce9")),
    ("text-charset", lambda email: email.text("text", "utf-8\r\nBcc: victim@example.com")),
    ("text-unknown-charset", lambda email: email.text("text", "no-such-charset")),
]


@pytest.mark.parametrize(
    "build", [build for _, build in HOSTILE_VALUES], ids=[label for label, _ in HOSTILE_VALUES]
)
def test_a_hostile_value_never_reaches_the_wire_as_a_header(
    build: Callable[[Email], Email],
) -> None:
    email = build(_email().text("body"))

    rendered = _render_or_refuse(email)

    if rendered is not None:
        assert "Bcc" not in _headers_of(rendered)
        assert all(len(line) <= 998 for line in rendered.split(b"\r\n"))


ADDRESS_SETTERS: Final[list[tuple[str, Callable[[Email, str], Email]]]] = [
    ("from", lambda email, value: email.from_(value)),
    ("add_from", lambda email, value: email.add_from(value)),
    ("reply_to", lambda email, value: email.reply_to(value)),
    ("add_reply_to", lambda email, value: email.add_reply_to(value)),
    ("to", lambda email, value: email.to(value)),
    ("add_to", lambda email, value: email.add_to(value)),
    ("cc", lambda email, value: email.cc(value)),
    ("add_cc", lambda email, value: email.add_cc(value)),
    ("bcc", lambda email, value: email.bcc(value)),
    ("add_bcc", lambda email, value: email.add_bcc(value)),
    ("sender", lambda email, value: email.sender(value)),
    ("return_path", lambda email, value: email.return_path(value)),
]

HOSTILE_ADDRESSES: Final = [
    INJECTED,
    "x@example.com\nBcc: victim@example.com",
    "x@exa\x00mple.com",
    "x\udce9@example.com",
    "Name\r\nBcc: victim@example.com <x@example.com>",
    "=?utf-8?q?victim@example.com?= <x@example.com>",
    "x@" + "a" * 2000 + ".com",
]


@pytest.mark.parametrize(
    "set_address",
    [set_address for _, set_address in ADDRESS_SETTERS],
    ids=[label for label, _ in ADDRESS_SETTERS],
)
@pytest.mark.parametrize("value", HOSTILE_ADDRESSES, ids=range(len(HOSTILE_ADDRESSES)))
def test_a_hostile_address_never_adds_a_recipient(
    set_address: Callable[[Email, str], Email], value: str
) -> None:
    email = Email().from_("me@example.com").to("you@example.com").text("body")
    try:
        _ = set_address(email, value)
    except (InvalidArgumentError, LogicError) as error:
        _assert_clean_error(error)
        return

    rendered = _render_or_refuse(email)

    if rendered is not None:
        assert "Bcc" not in _headers_of(rendered)
        assert "victim@example.com" not in _addresses_of(rendered)


def test_a_hostile_path_is_refused_without_its_raw_value() -> None:
    email = _email().text("body").attach_from_path("/no/such\r\nBcc: victim@example.com\x00.txt")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = email.to_string()

    _assert_clean_error(caught.value)


def test_a_long_line_of_body_text_is_folded_for_the_wire() -> None:
    email = _email().text("word " * 4000).html("<p>" + "x" * 20000 + "</p>")

    rendered = b"".join(email.to_iterable())

    assert max(len(line) for line in rendered.split(b"\r\n")) <= 78
    parsed = BytesParser(policy=policy.default).parsebytes(rendered)
    html = next(part for part in parsed.walk() if part.get_content_type() == "text/html")
    assert _decoded(html).rstrip(b"\r\n") == b"<p>" + b"x" * 20000 + b"</p>"


def test_a_huge_attachment_from_a_path_is_rendered_in_pieces(tmp_path: Path) -> None:
    path = tmp_path / "huge.bin"
    data = bytes(range(256)) * (4 * 1024 * 4)  # 4 MiB
    _ = path.write_bytes(data)
    email = _email().text("body").attach_from_path(path)

    chunks = list(email.to_iterable())

    assert len(chunks) > 1
    parsed = BytesParser(policy=policy.default).parsebytes(b"".join(chunks))
    attachment = next(part for part in parsed.walk() if part.get_filename() == "huge.bin")
    assert _decoded(attachment) == data
