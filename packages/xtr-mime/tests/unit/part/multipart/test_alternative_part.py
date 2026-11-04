"""multipart/alternative: the same content in several forms, the preferred one last."""

from __future__ import annotations

from xtr_mime.part.multipart import AlternativePart


def test_constructor() -> None:
    part = AlternativePart()

    assert part.get_media_type() == "multipart"
    assert part.get_media_subtype() == "alternative"
