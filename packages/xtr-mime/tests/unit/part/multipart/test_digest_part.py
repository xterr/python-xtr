"""multipart/digest: a collection of whole messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_mime.part import MessagePart
from xtr_mime.part.multipart import DigestPart

if TYPE_CHECKING:
    from collections.abc import Iterator


@final
class _FakeRawMessage:
    """A message that is only bytes; its to_string and to_iterable agree."""

    def to_string(self) -> str:
        return "Subject: digest\r\n\r\nbody\r\n"

    def to_iterable(self) -> Iterator[bytes]:
        yield self.to_string().encode()


def test_the_fake_renders_the_same_bytes_either_way() -> None:
    message = _FakeRawMessage()

    assert b"".join(message.to_iterable()) == message.to_string().encode()


def test_constructor() -> None:
    a, b = MessagePart(_FakeRawMessage()), MessagePart(_FakeRawMessage())

    part = DigestPart(a, b)

    assert part.get_media_type() == "multipart"
    assert part.get_media_subtype() == "digest"
    assert part.get_parts() == [a, b]
    assert part.to_string().count("Subject: digest") == 2
