"""The text object sections and context blocks are written with."""

from __future__ import annotations

__all__ = ["text_object"]


def text_object(text: str, markdown: bool, emoji: bool, verbatim: bool) -> dict[str, object]:
    """Render ``text`` as ``mrkdwn`` with its ``verbatim`` flag, or plain with its ``emoji`` one.

    Each flag exists for one type only, so the other is never sent.
    """
    if markdown:
        return {"type": "mrkdwn", "text": text, "verbatim": verbatim}
    return {"type": "plain_text", "text": text, "emoji": emoji}
