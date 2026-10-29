"""Plain data: what a normalizer makes of a value, and what an encoder writes as text."""

from __future__ import annotations

from typing import TypeAlias

from pydantic import JsonValue

__all__ = ["NormalizedValue"]

NormalizedValue: TypeAlias = JsonValue
"""A value made only of what JSON holds: booleans, numbers, strings, lists and objects keyed by
strings, nested, and ``None``.

Where the two halves of a serializer meet. Normalizers turn objects into this and back, knowing
nothing of formats; encoders turn this into text and back, knowing nothing of classes. Lists and
dictionaries only, not any sequence or mapping: each value has a single plain form, so what a
tuple or a set becomes, and how it is read back as one, is settled by the normalizer, the step
that knows the type it was declared with.

It is pydantic's ``JsonValue`` itself, the type the JSON encoder checks data against. The encoder
refuses more than the type does, though: NaN and the infinities, which JSON has no form for, and
what its parser would not read back. Data passes when it nests no more than about 200 levels
deep, holds no integer longer than 4300 characters, its sign included, and no string with a lone
surrogate.
"""
