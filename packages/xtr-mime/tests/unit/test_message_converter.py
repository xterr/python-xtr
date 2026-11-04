"""Turning a message with a simple body tree back into an email a provider's API can take.

Upstream compares the two emails with object equality; here they are compared by what an
email holds: headers, bodies and charsets, and the shape of each attachment.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from xtr_clock import MockClock

from tests.support.dkim_extra import needs_dkim_extra
from tests.support.part_shape import shape
from tests.support.smime_extra import needs_smime_extra
from xtr_mime import Email, Message, MessageConverter
from xtr_mime.exception import MimeRuntimeError
from xtr_mime.part import AlternativePart, DataPart, MixedPart, RelatedPart, TextPart

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mime.part import AbstractPart

GIF: Final = (Path(__file__).parents[1] / "fixtures" / "mimetypes" / "test.gif").read_bytes()
HTML: Final = 'HTML content <img src="cid:test.jpg" />'
TOO_COMPLEX: Final = (
    'Unable to create an Email from an instance of "xtr_mime.Message" as the body is too complex.'
)
S_MIME: Final = (
    'Unable to create an Email from an instance of "xtr_mime.Message" as the body is signed or '
    "encrypted with S/MIME: only the whole message can be sent."
)


def _base() -> Email:
    return Email().from_("fabien@example.com").to("you@example.com")


def _inline() -> DataPart:
    return DataPart(GIF, "test.jpg", "image/gif").as_inline()


def _attached() -> DataPart:
    return DataPart(GIF, "test_attached.jpg", "image/gif")


def _summary(email: Email) -> tuple[object, ...]:
    return (
        email.get_headers().to_array(),
        email.get_text_body(),
        email.get_text_charset(),
        email.get_html_body(),
        email.get_html_charset(),
        [shape(part) for part in email.get_attachments()],
    )


def _assert_conversion(expected: Email, *, dkim: bool = False) -> None:
    message = Message(expected.get_headers(), expected.get_body())
    if dkim:
        message = _dkim_signed(message)

    converted = MessageConverter.to_email(message)

    html = expected.get_html_body()
    if html:
        assert isinstance(html, str)
        pattern = re.escape(html).replace(re.escape("cid:test.jpg"), "cid:.+")
        assert re.fullmatch(pattern, str(converted.get_html_body()))
        _ = expected.html("HTML content")
        _ = converted.html("HTML content")
    if dkim:
        # The signed headers are the ones the message is sent with, the signature above them.
        assert converted.get_headers().has("DKIM-Signature")
        assert _summary(converted)[1:] == _summary(expected)[1:]
    else:
        assert _summary(converted) == _summary(expected)


def _dkim_signed(message: Message) -> Message:
    # Imported here: without the dkim extra it does not import, and only its cases skip.
    from tests.support import dkim_signing  # noqa: PLC0415 -- see above.

    return dkim_signing.signer().sign(message)


def _s_mime_signed(tmp_path: Path) -> Message:
    # Imported here: without the smime extra it does not import, and only its cases skip.
    from tests.support import smime_signing  # noqa: PLC0415 -- see above.

    return smime_signing.signer(tmp_path).sign(smime_signing.email())


def test_to_email_returns_an_email_as_it_is() -> None:
    email = _base()

    assert MessageConverter.to_email(email) is email


def test_to_email_keeps_the_clock_of_the_message() -> None:
    clock = MockClock(datetime(2005, 10, 15, 12, 34, 56, tzinfo=UTC))
    message = Message(_base().get_headers(), TextPart("text content"), clock=clock)

    converted = MessageConverter.to_email(message)

    date = converted.get_prepared_headers().get_header_body("Date")
    assert date == datetime(2005, 10, 15, 12, 34, 56, tzinfo=UTC)


CONVERSIONS: Final[list[tuple[str, Callable[[Email], Email]]]] = [
    ("text", lambda email: email.text("text content")),
    ("html", lambda email: email.html(HTML)),
    ("text-html", lambda email: email.text("text content").html(HTML)),
    ("text-html-inline", lambda email: email.text("text content").html(HTML).add_part(_inline())),
    (
        "text-html-attached",
        lambda email: email.text("text content").html(HTML).add_part(_attached()),
    ),
    (
        "text-html-inline-attached",
        lambda email: (
            email.text("text content").html(HTML).add_part(_inline()).add_part(_attached())
        ),
    ),
    ("text-attached", lambda email: email.text("text content").add_part(_attached())),
    ("html-attached", lambda email: email.html(HTML).add_part(_attached())),
    ("html-inline", lambda email: email.html(HTML).add_part(_inline())),
    (
        "text-inline-unreferenced",
        lambda email: email.text("text content").add_part(
            DataPart(GIF, "test_attached.jpg", "image/gif").as_inline()
        ),
    ),
]


@pytest.mark.parametrize(
    "build", [build for _, build in CONVERSIONS], ids=[label for label, _ in CONVERSIONS]
)
def test_to_email(build: Callable[[Email], Email]) -> None:
    _assert_conversion(build(_base().__copy__()))


@needs_dkim_extra
@pytest.mark.parametrize(
    "build", [build for _, build in CONVERSIONS], ids=[label for label, _ in CONVERSIONS]
)
def test_to_email_reads_the_body_a_dkim_signature_covers(build: Callable[[Email], Email]) -> None:
    _assert_conversion(build(_base().__copy__()), dkim=True)


@needs_smime_extra
def test_to_email_refuses_a_body_signed_with_s_mime(tmp_path: Path) -> None:
    signed = _s_mime_signed(tmp_path)

    with pytest.raises(MimeRuntimeError, match=f"^{re.escape(S_MIME)}$"):
        _ = MessageConverter.to_email(signed)


@needs_dkim_extra
@needs_smime_extra
def test_to_email_refuses_an_s_mime_body_signed_with_dkim(tmp_path: Path) -> None:
    signed = _s_mime_signed(tmp_path)

    with pytest.raises(MimeRuntimeError, match=f"^{re.escape(S_MIME)}$"):
        _ = MessageConverter.to_email(_dkim_signed(signed))


def test_to_email_keeps_the_charset_of_each_body() -> None:
    body = AlternativePart(TextPart("text", "iso-8859-1"), TextPart("html", "iso-8859-2", "html"))

    email = MessageConverter.to_email(Message(None, body))

    assert (email.get_text_charset(), email.get_html_charset()) == ("iso-8859-1", "iso-8859-2")


def test_to_email_reads_utf8_for_a_body_without_a_charset() -> None:
    email = MessageConverter.to_email(Message(None, TextPart(b"text", None)))

    assert (email.get_text_body(), email.get_text_charset()) == (b"text", "utf-8")


TOO_COMPLEX_BODIES: Final[list[tuple[str, Callable[[], AbstractPart | None]]]] = [
    ("no body", lambda: None),
    ("empty mixed", MixedPart),
    ("calendar", lambda: TextPart("event", "utf-8", "calendar")),
    ("attachment only", lambda: DataPart(b"data")),
    ("alternative of one", lambda: AlternativePart(TextPart("text"))),
    (
        "alternative html first",
        lambda: AlternativePart(TextPart("<b>", "utf-8", "html"), TextPart("text")),
    ),
    ("related with an attachment first", lambda: RelatedPart(DataPart(b"a"), DataPart(b"b"))),
    ("mixed with an attachment first", lambda: MixedPart(DataPart(b"a"), DataPart(b"b"))),
    ("mixed with text after the body", lambda: MixedPart(TextPart("text"), TextPart("more"))),
    ("related with text after the body", lambda: RelatedPart(TextPart("text"), TextPart("more"))),
]


@pytest.mark.parametrize(
    "build",
    [build for _, build in TOO_COMPLEX_BODIES],
    ids=[label for label, _ in TOO_COMPLEX_BODIES],
)
def test_to_email_refuses_a_body_too_complex(build: Callable[[], AbstractPart | None]) -> None:
    with pytest.raises(MimeRuntimeError, match=f"^{re.escape(TOO_COMPLEX)}$"):
        _ = MessageConverter.to_email(Message(None, build()))


def test_to_email_names_the_class_of_the_message_refused() -> None:
    class CustomMessage(Message):
        pass

    with pytest.raises(MimeRuntimeError, match=r'instance of ".*CustomMessage"'):
        _ = MessageConverter.to_email(CustomMessage())
