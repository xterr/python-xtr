"""Reading and writing what a subject keeps, whether its accessors are plain or coroutines.

The workflow tests run once with each kind of subject; these let a test set
up a marking, or read the one a workflow stored, without caring which kind
it was handed.
"""

from __future__ import annotations

from typing import TypeAlias, assert_never

from tests.fixtures.subject import AsyncSubject, Subject

__all__ = ["SUBJECT_TYPES", "AnySubject", "keep", "kept_by"]

AnySubject: TypeAlias = Subject | AsyncSubject

SUBJECT_TYPES: tuple[type[AnySubject], ...] = (Subject, AsyncSubject)


async def keep(subject: AnySubject, marking: object) -> None:
    """Have ``subject`` keep ``marking``, through its own setter."""
    match subject:
        case Subject():
            subject.set_marking(marking)
        case AsyncSubject():
            await subject.set_marking(marking)
        case _:
            assert_never(subject)


async def kept_by(subject: AnySubject) -> object:
    """Return what ``subject`` keeps, through its own getter."""
    match subject:
        case Subject():
            return subject.get_marking()
        case AsyncSubject():
            return await subject.get_marking()
        case _:
            assert_never(subject)
