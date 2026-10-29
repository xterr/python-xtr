"""The context key the JSON encoder reads.

Kept apart from the encoder, so the context builder that sets it can be imported without it.
Prefixed with ``json_``: one context carries the options of every step, and this one must not be
mistaken for a normalizer's.
"""

from __future__ import annotations

from typing import Final

__all__ = ["JSON_INDENT"]

JSON_INDENT: Final = "json_indent"
"""How many spaces each level of nesting is indented by, for JSON a person is to read.

``None``, as when the key is absent, writes the whole value on one line, for JSON that only a
program reads. At most 10: a wider indent makes no text easier to read, and one wide enough to
exhaust memory would stop the process rather than fail the call.
"""
