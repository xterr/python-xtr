"""Which types a normalizer handles, and whether its answer for them can be remembered."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, TypeAlias

__all__ = ["SupportedTypes"]

SupportedTypes: TypeAlias = Mapping[type | Literal["*", "object"], bool | None]
"""The types a normalizer or a denormalizer handles in one format, as it reports them.

Lets a serializer holding many normalizers find the one for a type without asking each of them
about every value. A key names what is handled: a class, which stands for its subclasses too;
``"object"``, which stands for every class; or ``"*"``, which stands for anything at all,
including types that are not classes, such as ``int | None``. Its value says whether that is
handled and, if so, what the answer of ``supports_normalization`` or
``supports_denormalization`` for it depends on:

- ``True``: on the type and the format alone, so a serializer may ask once per type and remember
  the answer;
- ``False``: on the value or the context too, so it asks every time;
- ``None``: it is not handled.

A type no key covers is not handled. A key naming the type itself is read before any other, so
``None`` there settles it; among the keys that cover a type through its subclasses, the first
reported counts, so ``None`` on a narrower key is passed over when a broader one is reported
before it. List the narrower keys first.
"""
