"""What every multipart shares: its parts, a boundary of its own, and the tree it renders."""

from __future__ import annotations

import re

from tests.support.rendered_part import read_part
from tests.support.wire import decode_parameters
from xtr_mime.part import DataPart, TextPart
from xtr_mime.part.multipart import AlternativePart, MixedPart


def _boundary(part: MixedPart | AlternativePart) -> str:
    return decode_parameters(part.get_prepared_headers().to_array()[0])["boundary"]


def test_the_parts_are_kept_in_order() -> None:
    text, html = TextPart("text"), TextPart("<b>html</b>", "utf-8", "html")

    assert AlternativePart(text, html).get_parts() == [text, html]


def test_the_boundary_is_eight_url_safe_characters_kept_for_the_part() -> None:
    part = MixedPart(TextPart("content"))

    boundary = _boundary(part)

    assert re.fullmatch(r"[A-Za-z0-9_-]{8}", boundary)
    assert _boundary(part) == boundary
    assert _boundary(MixedPart()) != boundary


def test_the_body_is_every_part_between_boundaries() -> None:
    part = MixedPart(TextPart("text"), DataPart("data", "file.bin"))
    boundary = _boundary(part)

    body = part.body_to_string()

    assert body.startswith(f"--{boundary}\r\n")
    assert body.endswith(f"\r\n--{boundary}--\r\n")
    assert body.count(f"--{boundary}\r\n") == 2
    assert b"".join(part.body_to_iterable()) == body.encode()


def test_the_tree_reads_back() -> None:
    part = MixedPart(
        AlternativePart(TextPart("text"), TextPart("<b>html</b>", "utf-8", "html")),
        DataPart("data", "file.bin"),
    )

    message = read_part(part)

    assert [p.get_content_type() for p in message.walk()] == [
        "multipart/mixed",
        "multipart/alternative",
        "text/plain",
        "text/html",
        "application/octet-stream",
    ]
    assert "MIME-Version" not in part.to_string()
    assert part.to_string().encode() == b"".join(part.to_iterable())


def test_as_debug_string() -> None:
    part = MixedPart(
        AlternativePart(TextPart("text"), TextPart("html", "utf-8", "html")),
        DataPart("data", "file.bin"),
    )

    assert part.as_debug_string() == (
        "multipart/mixed\n"
        "  └ multipart/alternative\n"
        "  |  └ text/plain charset: utf-8\n"
        "  |  └ text/html charset: utf-8\n"
        "  └ application/octet-stream disposition: attachment filename: file.bin"
    )
