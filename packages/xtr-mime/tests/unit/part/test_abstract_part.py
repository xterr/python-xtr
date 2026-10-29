"""What every part shares: its own headers, the prepared ones, and the rendering through them.

Upstream's cases here are all about serialization, which has no counterpart: a part is not
serialized, and a queued email travels as a snapshot. These cover the base class instead,
through the simplest part.
"""

from __future__ import annotations

from typing import final

import pytest
from typing_extensions import override

from tests.support.wire import decode_parameters
from xtr_mime.exception import RfcComplianceError
from xtr_mime.header import UnstructuredHeader
from xtr_mime.part import AbstractPart, TextPart


@final
class _WrittenHeader(UnstructuredHeader):
    """A header that writes itself as given, as a header class of the caller's may."""

    __slots__ = ("_written",)

    def __init__(self, written: str) -> None:
        super().__init__("X-Written", "value")
        self._written = written

    @override
    def to_string(self) -> str:
        return self._written


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


def test_a_header_written_by_the_caller_is_carried_as_written() -> None:
    part = TextPart("content")
    _ = part.get_headers().add(_WrittenHeader("X-Written: as\r\n given"))

    assert part.to_string().startswith("X-Written: as\r\n given\r\nContent-Type: ")


@pytest.mark.parametrize(
    "written",
    [
        pytest.param("X-Written value", id="no colon"),
        pytest.param("X Written: value", id="not a name"),
        pytest.param("X-Written: a\r\nInjected: 1", id="a line of its own"),
        pytest.param("X-Written: a\x00b", id="a control character"),
    ],
)
def test_a_header_that_is_not_a_field_is_refused(written: str) -> None:
    part = TextPart("content")
    _ = part.get_headers().add(_WrittenHeader(written))

    with pytest.raises(RfcComplianceError):
        _ = part.to_string()
