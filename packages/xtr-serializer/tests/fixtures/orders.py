"""An order, spelled as a model, a dataclass and a typed dict, with the values JSON lacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from typing_extensions import TypedDict  # pydantic reads typing's only from Python 3.12

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "Cart",
    "CartItem",
    "Customer",
    "Item",
    "LaxItem",
    "Node",
    "Order",
    "Receipt",
    "Shipment",
    "Status",
    "StrictCart",
    "Ticket",
]


class Status(Enum):
    """An enum by value: JSON carries the value, the declared type brings the member back."""

    OPEN = 1
    SHIPPED = 2


class Item(BaseModel):
    """A line of an order; strict and closed, so a wrong or unknown field is refused."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, extra="forbid")

    sku: str
    price: int


class Order(BaseModel):
    """A model with every value JSON has no type for, and bytes in their exact form."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True, ser_json_bytes="base64", val_json_bytes="base64"
    )

    id: UUID
    placed_at: datetime
    total: Decimal
    status: Status
    signature: bytes
    dimensions: tuple[int, int, int]
    tags: frozenset[str]
    items: list[Item]


@dataclass(frozen=True)
class Shipment:
    """A dataclass with no configuration of its own: the normalizer's governs it."""

    id: UUID
    sent_on: date
    sent_at: datetime
    transit: timedelta
    weight: Decimal
    status: Status
    label: bytes
    route: tuple[str, ...]
    zones: frozenset[int]


class Receipt(TypedDict):
    """A typed dict: also governed by the normalizer's configuration."""

    number: int
    issued_at: datetime
    seal: bytes


class LaxItem(BaseModel):
    """A model whose own configuration converts, so ``"1"`` reads as ``1``."""

    sku: str
    price: int


class Cart(BaseModel):
    """Several items, to locate an error inside a list."""

    items: list[Item]


class StrictCart(BaseModel):
    """A closed model: data with a field it does not declare is refused."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    owner: str


class CartItem(BaseModel):
    """A lax, open model, for the options that override its configuration."""

    sku: str
    price: int


class Customer(BaseModel):
    """A field written under an alias, and fields with defaults and empty values."""

    full_name: str = Field(alias="fullName")
    nickname: str | None = None
    country: str = "RO"


@dataclass
class Node:
    """An object that may hold itself."""

    children: list[Node] = field(default_factory=list)


class Ticket(BaseModel):
    """A validator that reads the call's context."""

    code: str

    @field_validator("code")
    @classmethod
    def _prefix(cls, value: str, info: ValidationInfo) -> str:
        context = cast("Mapping[str, str]", info.context or {})
        return f"{context.get('prefix', '')}{value}"
