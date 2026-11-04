"""The text of an HTML body: its markup stripped, what is not content dropped."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Final, final

from typing_extensions import override

__all__ = ["DefaultHtmlToTextConverter"]

_HIDDEN: Final = frozenset({"head", "script", "style"})
"""Elements whose text is never content: the document's metadata, its scripts and styles."""

_HORIZONTAL_SPACE: Final = re.compile(r"[^\S\n]+")
_BLANK_LINES: Final = re.compile(r"\n{3,}")

_LONG_REFERENCE: Final = re.compile(r"&#(?:([xX])([0-9a-fA-F]{7,})|([0-9]{8,}))(;?)")
"""A numeric character reference written with more digits than U+10FFFF, the last code point."""


@final
class DefaultHtmlToTextConverter:
    """Strips the tags of an HTML body, keeping the text a reader would see.

    The head, scripts and styles are dropped with what they hold, comments and declarations
    vanish, and character references are decoded; a numeric one past U+10FFFF, however many
    digits it is written with, reads as U+FFFD. Whitespace is collapsed: each line is trimmed
    and a run of whitespace inside it becomes one space, runs of blank lines become one blank
    line, and the whole text is trimmed, so the indentation of a ``<pre>`` block is lost. An
    element that is opened but never closed hides nothing: its text is kept.

    The HTML is read by the standard library's tolerant parser, so malformed or hostile markup
    converts without an error, in time that grows with its length.
    """

    __slots__ = ()

    def convert(self, html: str, charset: str) -> str:
        """Return the text ``html`` reads as."""
        del charset  # the text stays a str; the part carrying it encodes it in its charset
        collector = _TextCollector()
        collector.feed(_LONG_REFERENCE.sub(_shortened, html))
        collector.close()
        text = collector.text().replace("\r\n", "\n").replace("\r", "\n")
        lines = (_HORIZONTAL_SPACE.sub(" ", line).strip() for line in text.split("\n"))
        return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def _shortened(reference: re.Match[str]) -> str:
    """Return ``reference`` without its leading zeros, or U+FFFD when it names no code point.

    The parser reads the digits of a reference with ``int()``, which refuses more than a few
    thousand of them and, where an application lifts that limit, takes time growing faster than
    their count. Leading zeros change no number, and a number with more digits than U+10FFFF
    — 6 in hexadecimal, 7 in decimal — is past the last code point: a browser reads it as
    U+FFFD, and so does the converter, without reading its digits. No reference reaches the
    parser with more digits than U+10FFFF has.

    The rewrite comes before the parser, so it reaches the text of a raw text element too —
    ``<xmp>``, ``<plaintext>`` — which a browser shows as written; only a reference this long
    reads differently there.
    """
    marker, hexadecimal, decimal, end = reference.groups("")
    digits = (hexadecimal or decimal).lstrip("0") or "0"
    if len(digits) > (6 if marker else 7):
        return "\N{REPLACEMENT CHARACTER}"
    return f"&#{marker}{digits}{end}"


class _TextCollector(HTMLParser):
    """Collects the text of a document, setting aside what a hidden element holds."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._kept: list[str] = []
        self._set_aside: list[str] = []
        self._hidden_by: str | None = None

    def text(self) -> str:
        """Return the text collected — with that of a hidden element never closed."""
        return "".join(self._kept) + "".join(self._set_aside)

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._hidden_by is None and tag in _HIDDEN:
            self._hidden_by = tag

    @override
    def handle_endtag(self, tag: str) -> None:
        # The first end tag of the hidden element closes it, whatever was opened inside.
        if tag == self._hidden_by:
            self._hidden_by = None
            self._set_aside.clear()

    @override
    def handle_data(self, data: str) -> None:
        (self._kept if self._hidden_by is None else self._set_aside).append(data)

    @override
    def parse_marked_section(self, i: int, report: bool = True) -> int:
        """Read a ``<![...[`` section, as a bogus comment when its keyword is unknown.

        Before the parser fixes released in 2025, an unknown keyword raised; the fixed parser
        reads such a section to the next ``>`` and never calls this, so the fallback does the
        same — to the end of the input when there is no ``>``, which keeps it linear.
        """
        try:
            return super().parse_marked_section(i, report)
        except AssertionError:
            end = self.rawdata.find(">", i + 3)
            return len(self.rawdata) if end < 0 else end + 1
