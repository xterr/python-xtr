"""Subjects keeping their marking in attributes alone, with no accessors.

Each attribute is declared and left unset until a store writes it.
"""

# Leaving the declared attributes unset is what these subjects are for, so
# the check that every declared attribute is set is off here.
# pyright: reportUninitializedInstanceVariable=false

from __future__ import annotations

from typing import final


@final
class SubjectWithAttributes:
    # For a workflow.
    marking: dict[str, int]
    # For a state machine; a test may hand it a value object.
    place: object


class ParentWithAttribute:
    place: str


@final
class ChildInheritingAttribute(ParentWithAttribute):
    pass


@final
class SubjectWithSlot:
    # A slot and nothing else: no annotation declares it, no default sets it.
    __slots__ = ("marking",)
