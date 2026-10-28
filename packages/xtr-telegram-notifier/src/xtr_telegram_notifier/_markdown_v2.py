"""Escaping a message for the MarkdownV2 parse mode."""

from __future__ import annotations

import re
from typing import Final

__all__ = ["escape_markdown_v2"]

# Matched in order: an already escaped character, kept; a spoiler marker, kept; a block
# quotation (">" or "**>" opening a line), kept; a custom emoji ("!["), kept; and a reserved
# character outside of those, the one group captured and escaped.
_RESERVED: Final = re.compile(r"\\[\x01-\x7E]|\|\||^(?:\*\*)?>|!\[|([.!#+\-=|{}>])", re.MULTILINE)


def escape_markdown_v2(text: str) -> str:
    """Escape the characters the bot API rejects unescaped, leaving the markup alone.

    Paired markers (``*bold*``, ``_italic_``, `` `code` ``, ``~strike~``,
    ``||spoiler||``, ``[link](url)``), block quotations and custom emojis are
    kept, so a message written in MarkdownV2 is sent as written, while a plain
    sentence ending in ``.`` or ``!`` is no longer refused.
    """
    return _RESERVED.sub(lambda match: match[0] if match[1] is None else f"\\{match[1]}", text)
