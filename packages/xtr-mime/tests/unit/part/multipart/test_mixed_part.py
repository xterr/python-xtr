"""multipart/mixed: a body followed by attachments.

Upstream's serialization cases have no counterpart: a part is not serialized.
"""

from __future__ import annotations

from xtr_mime.part.multipart import MixedPart


def test_constructor() -> None:
    part = MixedPart()

    assert part.get_media_type() == "multipart"
    assert part.get_media_subtype() == "mixed"
