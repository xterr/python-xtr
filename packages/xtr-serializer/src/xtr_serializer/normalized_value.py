"""Plain data: what a normalizer makes of a value, and what an encoder writes as text."""

from __future__ import annotations

from typing import TypeAlias

__all__ = ["NormalizedValue"]

NormalizedValue: TypeAlias = (
    bool | int | float | str | list["NormalizedValue"] | dict[str, "NormalizedValue"] | None
)
"""A value made only of what JSON holds: booleans, numbers, strings, lists and objects keyed by
strings, nested to any depth, and ``None``.

Where the two halves of a serializer meet. Normalizers turn objects into this and back, knowing
nothing of formats; encoders turn this into text and back, knowing nothing of classes. Lists and
dictionaries only, not any sequence or mapping: each value has a single plain form, so what a
tuple or a set becomes, and how it is read back as one, is settled by the normalizer, the step
that knows the type it was declared with.
"""
