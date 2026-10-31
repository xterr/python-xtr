"""Describe a part tree by what it holds, so two trees built apart can be compared.

Parts have no equality of their own — a multipart's boundary is random — so a test compares
their shape: each part's kind, its debug description, and a leaf's name and content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mime.part import AbstractMultipartPart, TextPart

if TYPE_CHECKING:
    from xtr_mime.part import AbstractPart

__all__ = ["shape"]


def shape(part: AbstractPart) -> object:
    """Return a value equal for two parts built the same way."""
    if isinstance(part, AbstractMultipartPart):
        return (type(part).__name__, [shape(child) for child in part.get_parts()])
    if isinstance(part, TextPart):
        return (type(part).__name__, part.as_debug_string(), part.get_name(), part.get_body())
    return (type(part).__name__, part.as_debug_string())
