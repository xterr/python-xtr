"""The body an email's text, HTML and attachments are put together into."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import BinaryIO

import pytest

from xtr_mime._email_body import NO_BODY, assemble_body
from xtr_mime.exception import InvalidArgumentError, LogicError
from xtr_mime.part import AlternativePart, DataPart, MixedPart, RelatedPart, TextPart


@dataclass
class _Content:
    """What an email hands over: each body with its charset, and the attachments."""

    text: str | bytes | BinaryIO | None = None
    text_charset: str | None = None
    html: str | bytes | BinaryIO | None = None
    html_charset: str | None = None
    attachments: list[DataPart] = field(default_factory=list[DataPart])

    def get_text_body(self) -> str | bytes | BinaryIO | None:
        return self.text

    def get_text_charset(self) -> str | None:
        return self.text_charset

    def get_html_body(self) -> str | bytes | BinaryIO | None:
        return self.html

    def get_html_charset(self) -> str | None:
        return self.html_charset

    def get_attachments(self) -> list[DataPart]:
        return self.attachments


def _html_of(part: object) -> str | bytes:
    assert isinstance(part, TextPart)
    return part.get_body()


def test_nothing_to_put_together_is_refused() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_BODY)}$"):
        _ = assemble_body(_Content())


def test_a_text_alone_is_the_body() -> None:
    body = assemble_body(_Content(text="hello", text_charset="iso-8859-1"))

    assert isinstance(body, TextPart)
    assert body.get_body() == "hello"


def test_an_html_alone_is_the_body_in_utf8_by_default() -> None:
    body = assemble_body(_Content(html="<p>hello</p>"))

    assert isinstance(body, TextPart)
    assert body.get_media_subtype() == "html"
    assert body.get_prepared_headers().get_header_parameter("Content-Type", "charset") == "utf-8"


def test_text_and_html_are_alternatives() -> None:
    body = assemble_body(_Content(text="hello", html="<p>hello</p>"))

    assert isinstance(body, AlternativePart)


def test_attachments_alone_are_mixed() -> None:
    attachment = DataPart(b"x", "x.txt")

    body = assemble_body(_Content(attachments=[attachment]))

    assert isinstance(body, MixedPart)
    assert body.get_parts() == [attachment]


def test_an_attachment_the_html_does_not_show_goes_after_the_html() -> None:
    attachment = DataPart(b"x", "x.txt")

    body = assemble_body(_Content(html='<img src="cid:other.gif">', attachments=[attachment]))

    assert isinstance(body, MixedPart)
    assert body.get_parts()[1] is attachment
    assert _html_of(body.get_parts()[0]) == '<img src="cid:other.gif">'


def test_an_attachment_the_html_shows_is_inlined_and_referred_to_by_its_content_id() -> None:
    image = DataPart(b"G", "a.gif")

    body = assemble_body(_Content(html='<img src="cid:a.gif">', attachments=[image]))

    assert isinstance(body, RelatedPart)
    assert body.get_parts()[1] is image
    assert image.get_disposition() == "inline"
    assert _html_of(body.get_parts()[0]) == f'<img src="cid:{image.get_content_id()}">'


def test_an_html_given_as_bytes_is_rewritten_as_bytes_in_its_charset() -> None:
    image = DataPart(b"G", "a.gif")
    html = '<img src="cid:a.gif"> é'.encode("iso-8859-1")

    body = assemble_body(_Content(html=html, html_charset="iso-8859-1", attachments=[image]))

    assert isinstance(body, RelatedPart)
    expected = f'<img src="cid:{image.get_content_id()}"> é'.encode("iso-8859-1")
    assert _html_of(body.get_parts()[0]) == expected


def test_an_html_is_not_read_in_its_charset_without_attachments() -> None:
    # Nothing to refer to: the body is taken as it is, and refused only when it is rendered.
    body = assemble_body(_Content(html=b"\xff", html_charset="utf-16"))

    assert _html_of(body) == b"\xff"


def test_an_html_in_an_unknown_charset_is_refused_when_there_are_attachments() -> None:
    content = _Content(html=b"<p>", html_charset="no-such", attachments=[DataPart(b"x")])

    with pytest.raises(InvalidArgumentError, match=r"^The charset 'no-such' is unknown\.$"):
        _ = assemble_body(content)


def test_an_html_its_charset_cannot_read_is_refused() -> None:
    html = '<img src="cid:a.gif">'.encode("utf-16-le") + b"\x00"
    content = _Content(html=html, html_charset="utf-16-le", attachments=[DataPart(b"x")])

    with pytest.raises(InvalidArgumentError, match=r'^The body is not "utf-16-le" text: '):
        _ = assemble_body(content)


def test_an_html_its_charset_cannot_write_back_is_refused() -> None:
    # The lone byte reads as a stand-in character, which UTF-16 cannot write back.
    html = '<img src="cid:a.gif">'.encode("utf-16-le") + b"\xd8"
    content = _Content(html=html, html_charset="utf-16-le", attachments=[DataPart(b"G", "a.gif")])

    with pytest.raises(InvalidArgumentError, match=r'^The body is not "utf-16-le" text: '):
        _ = assemble_body(content)


def test_the_charset_is_escaped_in_the_error() -> None:
    # The codecs read "utf-16-le\r\n" as UTF-16: the bytes, an odd count, are refused.
    content = _Content(html=b"<p>", html_charset="utf-16-le\r\n", attachments=[DataPart(b"x")])

    with pytest.raises(InvalidArgumentError) as caught:
        _ = assemble_body(content)

    assert str(caught.value).startswith('The body is not "utf-16-le\\r\\n" text: ')


def test_a_charset_holding_a_null_byte_is_refused() -> None:
    content = _Content(html=b"<p>", html_charset="utf-8\x00", attachments=[DataPart(b"x")])

    with pytest.raises(InvalidArgumentError) as caught:
        _ = assemble_body(content)

    assert str(caught.value) == ('The body is not "utf-8\\x00" text: embedded null character.')
