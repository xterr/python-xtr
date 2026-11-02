"""Classes ``debug:serializer`` describes: a dataclass, a model renaming its fields, and others."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, cast, final

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, PlainValidator
from pydantic_core import core_schema
from typing_extensions import override

from tests.fixtures.foreign import Money

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic.config import JsonDict

__all__ = [
    "Account",
    "Crossed",
    "Empty",
    "Misdescribed",
    "PriceLambda",
    "Release",
    "Shipment",
    "Untyped",
    "Version",
    "not_a_class",
]


@dataclass(frozen=True)
class Shipment:
    """A dataclass: each field written under its own name."""

    reference: str
    weight: float
    sent_at: datetime | None = None
    tags: list[str] = field(default_factory=list[str])
    kind: Literal["box", "letter"] = "box"


class Account(BaseModel):
    """A model renaming its fields: one alias both ways, one read and written under two names."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    owner_name: str = Field(alias="ownerName")
    balance: int = Field(default=0, validation_alias="balanceIn", serialization_alias="balanceOut")
    labels: dict[str, int] = Field(default_factory=dict[str, int])


@dataclass(frozen=True)
class Empty:
    """A dataclass with no field."""


class Untyped:
    """A class pydantic has no schema for."""


def not_a_class() -> None:
    """A function, which names no class."""


@final
class Version:
    """A class handing pydantic a schema of its own, which no JSON schema describes."""

    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        del source, handler
        return core_schema.no_info_plain_validator_function(
            cls.read, serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def read(cls, value: object) -> Version:
        return cls(str(value))

    @override
    def __str__(self) -> str:
        return self.text


def _money(value: object) -> Money:
    return Money(Decimal(str(value)), "EUR")


@dataclass(frozen=True)
class Release:
    """A dataclass holding a class pydantic has no JSON schema for."""

    name: str
    version: Version


@dataclass(frozen=True)
class PriceLambda:
    """A dataclass holding a foreign class, written by a lambda and read by a function."""

    price: Annotated[
        Money,
        PlainValidator(_money),
        # A lambda, as an application writes one: its parameter is typed by nothing.
        PlainSerializer(lambda money: str(money.amount)),  # pyright: ignore[reportAny] -- as above
    ]
    note: str = ""


class Crossed(BaseModel):
    """A model one of whose fields is read under the name of another."""

    first: str = Field(alias="second")
    second: str = ""


class Misdescribed(BaseModel):
    """A model whose JSON schema settings are of a kind pydantic refuses as it writes its schema."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        json_schema_extra=cast("JsonDict", cast("object", 3))
    )

    name: str
