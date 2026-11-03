"""What every part shares: its own headers, the prepared ones, and the rendering through them.

Upstream's cases here are all about serialization, which has no counterpart: a part is not
serialized, and xtr-mailer carries a queued email as plain data. These cover the base
class instead, through the simplest part.
"""

from __future__ import annotations

from tests.support.wire import decode_parameters
from xtr_mime.part import AbstractPart, TextPart


def test_a_content_type_parameter_creates_the_header_on_the_part() -> None:
    part = TextPart("content", None)

    _ = part.set_content_type_parameter("format", "flowed")

    assert part.get_headers().has("Content-Type")
    assert decode_parameters(part.get_prepared_headers().to_array()[0]) == {"format": "flowed"}


def test_the_prepared_content_type_follows_the_media_type() -> None:
    part = TextPart("content", None, "html")
    _ = part.get_headers().add_parameterized_header("Content-Type", "text/plain")

    assert part.get_prepared_headers().get_header_body("Content-Type") == "text/html"


def test_the_part_renders_as_headers_a_blank_line_and_the_body() -> None:
    part: AbstractPart = TextPart("content")

    rendered = b"".join(part.to_iterable())

    assert rendered == part.to_string().encode()
    assert rendered.endswith(b"\r\n\r\n" + part.body_to_string().encode())


def test_the_debug_string_is_the_media_type() -> None:
    assert TextPart("content", None).as_debug_string() == "text/plain"
