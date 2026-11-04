"""What the tests of a form read off the parts it builds."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_mime.part import TextPart

__all__ = ["transfer_encoding"]


def transfer_encoding(part: TextPart) -> object:
    return part.get_prepared_headers().get_header_body("Content-Transfer-Encoding")
