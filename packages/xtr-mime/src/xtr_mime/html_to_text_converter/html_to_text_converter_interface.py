"""What turns the HTML body of a message into its text body."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["HtmlToTextConverterInterface"]


@runtime_checkable
class HtmlToTextConverterInterface(Protocol):
    """Writes the text a plain-text mail reader shows in place of an HTML body.

    A message with only an HTML body reads poorly, or not at all, where HTML is not rendered;
    a converter derives the text alternative from the HTML, so the two never say different
    things.
    """

    def convert(self, html: str, charset: str) -> str:
        """Return the text ``html`` reads as.

        ``charset`` is the charset the HTML body is sent in, and the text body is sent in the
        same one.
        """
        ...
