"""multipart/related: a main part and the parts it refers to by content id.

Upstream's serialization cases have no counterpart: a part is not serialized.
"""

from __future__ import annotations

import re

from tests.support.rendered_part import read_part
from xtr_mime.header import IdentificationHeader
from xtr_mime.part import DataPart, TextPart
from xtr_mime.part.multipart import RelatedPart


def test_constructor() -> None:
    a = TextPart("content")
    b = TextPart("HTML content", "utf-8", "html")
    c = TextPart("HTML content again", "utf-8", "html")

    part = RelatedPart(a, b, c)

    assert part.get_media_type() == "multipart"
    assert part.get_media_subtype() == "related"
    assert part.get_parts() == [a, b, c]
    assert not a.get_headers().has("Content-ID")
    assert b.get_headers().has("Content-ID")
    assert c.get_headers().has("Content-ID")


def test_a_generated_content_id_is_random_hex_at_xtr() -> None:
    related = TextPart("related")

    _ = RelatedPart(TextPart("main"), related)

    header = related.get_headers().get("Content-ID")
    assert isinstance(header, IdentificationHeader)
    assert re.fullmatch(r"[0-9a-f]{32}@xtr", header.get_id() or "")


def test_a_part_with_a_content_id_keeps_it() -> None:
    related = TextPart("related")
    _ = related.get_headers().add_id_header("Content-ID", "kept@example.com")

    _ = RelatedPart(TextPart("main"), related)

    assert related.get_headers().get_header_body("Content-ID") == ["kept@example.com"]


def test_a_data_part_s_own_content_id_is_the_one_written() -> None:
    image = DataPart("image", "logo", "image/png").as_inline().set_content_id("logo@example.com")

    part = RelatedPart(TextPart('<img src="cid:logo@example.com">', "utf-8", "html"), image)

    rendered = read_part(part)
    assert [p["Content-ID"] for p in rendered.iter_parts()] == [None, "<logo@example.com>"]
