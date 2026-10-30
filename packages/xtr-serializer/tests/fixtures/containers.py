"""Containers of a subclass of a built-in one, and fields holding them."""

from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import dataclass
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, with_config
from typing_extensions import (  # pydantic reads typing's TypedDict from Python 3.12
    TypedDict,
    override,
)

from tests.fixtures.exact_values import Level

__all__ = [
    "Cabinet",
    "Counts",
    "Envelope",
    "Folder",
    "Grouped",
    "Identical",
    "Levelled",
    "Members",
    "Numbered",
    "Ordered",
    "Paired",
    "Queued",
    "Rows",
    "Signed",
    "Tallied",
]


class Levelled(NamedTuple):
    """A named tuple whose field takes an integer or the enum member equal to it."""

    x: int | Level


class Numbered(NamedTuple):
    """A named tuple holding an integer."""

    x: int


class Signed(NamedTuple):
    """A named tuple holding bytes."""

    signature: bytes


class Envelope(BaseModel):
    """A named tuple of bytes in a model whose configuration writes and reads bytes as text."""

    signed: Signed


@with_config(ConfigDict())
class Folder(TypedDict):
    """A named tuple of bytes in a typed dict whose own configuration takes bytes as text."""

    signed: Signed


@dataclass
class Cabinet:
    """A typed dict with a configuration of its own, held where it is declared."""

    folder: Folder


class Rows(list[object]):
    """A list of a subclass, comparing by the equality of a list."""


class Members(set[object]):
    """A set of a subclass, comparing by the equality of a set."""


class Identical(tuple[int, ...]):  # noqa: SLOT001 - holds nothing beside its members
    """A tuple of a subclass comparing by identity, which no copy read back equals."""

    @override
    def __eq__(self, other: object) -> bool:
        return other is self

    @override
    def __hash__(self) -> int:
        return id(self)


@dataclass
class Paired:
    """A named tuple held where it is declared."""

    p: Levelled


@dataclass
class Queued:
    """A deque."""

    q: deque[int | Level]


@dataclass
class Ordered:
    """An ordered dict."""

    d: OrderedDict[str, int | Level]


@dataclass
class Grouped:
    """A dict giving an empty list for a key it lacks."""

    d: defaultdict[str, list[int | Level]]


@dataclass
class Tallied:
    """A counter of text."""

    c: Counter[str]


@dataclass
class Counts:
    """A counter of integers, or of the enum members equal to them."""

    c: Counter[int | Level]
