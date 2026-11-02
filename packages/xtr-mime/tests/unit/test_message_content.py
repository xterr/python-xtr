"""A message writes an 8bit body at its top, and an attached message, as they were given.

Each message (see :mod:`tests.support.written_content`) is rendered both ways and read back as
a mail client reads it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.written_content import WRITTEN_CONTENTS, assert_written
from xtr_mime import MixedPart, TextPart

if TYPE_CHECKING:
    from tests.support.written_content import WrittenContent

_CONTENTS = pytest.mark.parametrize(
    "content", WRITTEN_CONTENTS.values(), ids=WRITTEN_CONTENTS.keys()
)


@_CONTENTS
def test_the_message_renders_the_same_bytes_both_ways(content: WrittenContent) -> None:
    message = content.build()

    assert message.to_string().encode("utf-8", "surrogateescape") == b"".join(message.to_iterable())


@_CONTENTS
def test_the_message_carries_its_body_as_written(content: WrittenContent) -> None:
    sent = b"".join(content.build().to_iterable())

    assert_written(content, sent)


@_CONTENTS
def test_the_message_as_text_carries_its_body_as_written(content: WrittenContent) -> None:
    sent = content.build().to_string().encode("utf-8", "surrogateescape")

    assert_written(content, sent)


@pytest.mark.parametrize("encoding", ["8bit", "binary"])
def test_a_top_level_text_body_is_written_as_inside_a_multipart(encoding: str) -> None:
    content = WRITTEN_CONTENTS[f"a top-level {encoding} text body"]
    inside = MixedPart(TextPart("Grüße\nzwei", encoding=encoding)).to_string()

    top_level = content.build().to_string()

    part = inside.split("\r\n--")[1].partition("\r\n\r\n")[2]
    assert top_level.endswith(f"\r\n\r\n{part}")
