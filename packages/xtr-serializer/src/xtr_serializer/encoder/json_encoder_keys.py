"""The context keys the JSON encoder reads.

Kept apart from the encoder, so the context builder that sets them can be imported without it.
Prefixed with ``json_``: one context carries the options of every step, and these must not be
mistaken for a normalizer's.
"""

from __future__ import annotations

from typing import Final

__all__ = ["JSON_ALLOW_INF_NAN", "JSON_INDENT"]

JSON_INDENT: Final = "json_indent"
"""How many spaces each level of nesting is indented by, for JSON a person is to read.

``None``, as when the key is absent, writes the whole value on one line, for JSON that only a
program reads.
"""

JSON_ALLOW_INF_NAN: Final = "json_allow_inf_nan"
"""Whether reading accepts ``NaN``, ``Infinity`` and ``-Infinity`` as numbers.

They are not JSON, but some writers put them down. Off when absent. Writing refuses them either
way: JSON has no notation for them, so text holding them would not be read back as it was meant
by any other reader.
"""
