"""The options one call hands to the serializer and to every step it takes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

__all__ = ["Context"]

Context: TypeAlias = Mapping[str, object]
"""Options for a single call, by name, each read by the step that knows it.

One mapping travels the whole way — serializer, normalizers, encoders — so a call can tune a step
it never deals with directly, such as how far the JSON is indented. Each step reads the keys it
knows and passes the rest on untouched. That is why values are ``object``: only the step that
owns a key knows the type of its value, and it checks what it reads. The context builders put a
context together with the type of each value checked where it is set.
"""
