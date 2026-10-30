"""Fields holding values that JSON alone would carry back changed, and one that keeps its zone."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from typing import Annotated, ClassVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    NaiveDatetime,
    PlainSerializer,
    ValidationInfo,
    field_validator,
)

from tests.fixtures.orders import Receipt
from xtr_serializer import ZonedDateTime
from xtr_serializer.exception import NotNormalizableValueError

__all__ = [
    "Amount",
    "Count",
    "Either",
    "Filed",
    "Ledger",
    "Level",
    "Local",
    "Loose",
    "Measured",
    "Meeting",
    "Note",
    "Refusing",
    "Scoped",
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


class Level(IntEnum):
    """An enum whose members are integers, and so fit an ``int`` field."""

    LOW = 1


@dataclass(eq=False)
class Ledger:
    """A dataclass compared by identity, which no copy read back equals."""

    value: int


@dataclass
class Either:
    """A union whose first member also takes what the second one writes."""

    value: int | Level


@dataclass
class Note:
    """Text."""

    value: str


@dataclass
class Stamp:
    """A datetime declared plainly: its offset is kept, its zone's name is not."""

    value: datetime


@dataclass
class Local:
    """A datetime declared naive."""

    value: NaiveDatetime


class Measured(BaseModel):
    """A model whose own configuration reads a decimal NaN back."""

    model_config: ClassVar[ConfigDict] = ConfigDict(allow_inf_nan=True)

    value: Decimal


class Scoped(BaseModel):
    """A model whose validator needs the tenant the context names."""

    value: int

    @field_validator("value")
    @classmethod
    def _in_tenant(cls, value: int, info: ValidationInfo) -> int:
        _ = cast("Mapping[str, object]", info.context)["tenant"]
        return value


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
