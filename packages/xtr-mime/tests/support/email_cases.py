"""The fixtures and parts the tests of an email build on, and the check an error is clean."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from xtr_mime import Email
from xtr_mime.part import DataPart, TextPart

if TYPE_CHECKING:
    from email.message import EmailMessage

__all__ = [
    "GIF",
    "NO_BODY",
    "TEST",
    "addressed_email",
    "assert_clean_error",
    "decoded",
    "file_part",
    "file_stream",
    "html_part",
    "image_part",
    "image_stream",
    "text_part",
]

FIXTURES: Final = Path(__file__).parents[1] / "fixtures"
TEST: Final = FIXTURES / "mimetypes" / "test"
GIF: Final = FIXTURES / "mimetypes" / "test.gif"
NO_BODY: Final = "A message must have a text or an HTML part or attachments."


def addressed_email() -> Email:
    return Email().from_("me@example.com").to("you@example.com")


def file_stream() -> io.BytesIO:
    return io.BytesIO(TEST.read_bytes())


def image_stream() -> io.BytesIO:
    return io.BytesIO(GIF.read_bytes())


def text_part() -> TextPart:
    return TextPart("text content")


def html_part() -> TextPart:
    return TextPart("html content", "utf-8", "html")


def file_part() -> DataPart:
    return DataPart(file_stream())


def image_part() -> DataPart:
    return DataPart(image_stream(), "test.gif")


def assert_clean_error(error: BaseException) -> None:
    text = str(error)
    assert not re.search(r"[\x00-\x1f\x7f\u2028\u2029]", text), text
    _ = text.encode("utf-8")  # no lone surrogate


def decoded(part: EmailMessage) -> bytes:
    return cast("bytes", part.get_payload(decode=True))
