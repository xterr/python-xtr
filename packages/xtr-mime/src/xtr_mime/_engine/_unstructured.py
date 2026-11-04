"""Unstructured text headers, written so they read back to the text they were given."""

from __future__ import annotations

import re
from email.header import Header
from typing import Final

from xtr_mime._header_reader import read_unstructured
from xtr_mime.exception import RfcComplianceError

from ._grammar import FOLD_WIDTH, body_of, refuse_forbidden
from ._policy import POLICY, UNSTRUCTURED, FoldedHeader

__all__ = ["encoded_words", "unstructured_header", "write_text"]

# The whitespace unstructured text is folded at.
_BLANKS: Final = re.compile(r"([ \t]+)")


def unstructured_header(name: str, value: str) -> FoldedHeader:
    """Build an unstructured header, folded once: the fold read back is the one kept."""
    refuse_forbidden(f"The {name} header", value)
    header = UNSTRUCTURED(name, value)
    # The engine reads an encoded word in the value as one: what it decodes to may hold what
    # the value itself did not.
    refuse_forbidden(f"The decoded {name} header", str(header))
    # A lenient reader takes "=?" for the start of an encoded word wherever it finds one — in
    # the middle of a word, after one that does not decode — where a mail client reads text:
    # a word holding it is always written encoded, so no reader decodes a part of it.
    if "=?" not in value:
        written = header.fold(policy=POLICY)
        if _reads_back_as(name, written, value):
            return FoldedHeader(name, str(header), written)
    folded = write_text(name, value)
    if not _reads_back_as(name, folded, value):
        raise RfcComplianceError(
            f"The {name} header would not read back to the text it was given: {folded!r}."
        )
    return FoldedHeader(name, value, folded)


def write_text(name: str, value: str) -> str:
    """Write unstructured text the package's folding would not write faithfully.

    A run of words holding non-ASCII text, or what a reader takes for an encoded word, is
    written as the package's legacy encoded words, the whitespace between its words encoded
    with them; every other word is written as it is, a word too long for a line on a line of
    its own. The field is folded only at the whitespace between words, so it unfolds to them.
    """
    tokens = _BLANKS.split(value.strip(" \t"))
    # (whitespace before, text, whether it is encoded): words alternate with whitespace.
    runs: list[tuple[str, str, bool]] = []
    for index in range(0, len(tokens), 2):
        gap, word = tokens[index - 1] if index else " ", tokens[index]
        encoded = not word.isascii() or "=?" in word
        if encoded and runs and runs[-1][2]:
            runs[-1] = (runs[-1][0], runs[-1][1] + gap + word, True)
        else:
            runs.append((gap, word, encoded))
    lines = [f"{name}:"]
    for gap, text, encoded in runs:
        words = encoded_words(text) if encoded else [text]
        for position, word in enumerate(words):
            # A reader drops the whitespace between two encoded words of one run.
            piece = (" " if position else gap) + word
            if len(lines[-1]) + len(piece) > FOLD_WIDTH:
                lines.append(piece)
            else:
                lines[-1] += piece
    return "\r\n".join(lines) + "\r\n"


def encoded_words(text: str) -> list[str]:
    return Header(text, "utf-8", maxlinelen=FOLD_WIDTH - 1).encode(linesep="\n").split()


def _reads_back_as(name: str, folded: str, value: str) -> bool:
    # Whitespace around the value reads back if it went into an encoded word, and is dropped
    # if it did not; either reading is the value.
    try:
        return read_unstructured(body_of(name, folded)) in {value, value.strip(" \t")}
    except ValueError:
        return False
