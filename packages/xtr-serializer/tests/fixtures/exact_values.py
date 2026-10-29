"""Fields holding values that JSON alone would carry back changed, and one that keeps its zone."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

from tests.fixtures.orders import Receipt
from xtr_serializer import ZonedDateTime
from xtr_serializer.exception import NotNormalizableValueError

__all__ = [
    "Amount",
    "Count",
    "Filed",
    "Loose",
    "Meeting",
    "Refusing",
    "Series",
    "Stamp",
]


@dataclass
class Amount:
    """A decimal, which has no NaN nor infinity in JSON."""

    value: Decimal


@dataclass
class Filed:
    """A typed dict held where it is declared, which a typed dict on its own, a dict, is not."""

    receipt: Receipt


@dataclass
class Count:
    """An integer."""

    value: int


@dataclass
class Stamp:
    """A datetime declared plainly: its offset is kept, its zone's name is not."""

    value: datetime


@dataclass
class Meeting:
    """A datetime declared to keep its zone."""

    starts_at: ZonedDateTime


@dataclass
class Series:
    """A sequence, which JSON carries as a list whatever it was."""

    value: Sequence[int]


@dataclass
class Loose:
    """Fields that declare nothing about what they hold."""

    items: list[object]
    mapping: dict[object, object]


def refuse(_value: object) -> str:
    """Refuse every value, in this package's words, at a place it names."""
    raise NotNormalizableValueError("has no plain form", path="value", error_type="refused")


@dataclass
class Refusing:
    """A field whose serializer refuses what it holds."""

    value: Annotated[int, PlainSerializer(refuse)]
