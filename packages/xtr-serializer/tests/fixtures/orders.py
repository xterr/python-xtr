"""An order, spelled as a model, a dataclass and a typed dict, with the values JSON lacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal, cast
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
    with_config,
)
from pydantic_core import PydanticCustomError
from typing_extensions import TypedDict  # pydantic reads typing's only from Python 3.12

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "Cart",
    "CartItem",
    "CheckedSlot",
    "ClosedParcel",
    "Customer",
    "Delivery",
    "Dispatch",
    "Handover",
    "Invoice",
    "Item",
    "LaxItem",
    "Letter",
    "Node",
    "Order",
    "Packet",
    "Parcel",
    "Pickup",
    "Receipt",
    "Shipment",
    "Slot",
    "Status",
    "StrictCart",
    "TaggedSlot",
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


class Slot(BaseModel):
    """A delivery slot whose validator refuses in words of its own, quoting no value."""

    start: int
    end: int

    @model_validator(mode="after")
    def _ordered(self) -> Slot:
        if self.end <= self.start:
            raise ValueError("end must follow start")
        return self


class CheckedSlot(BaseModel):
    """A delivery slot whose validator refuses with an assertion."""

    start: int
    end: int

    @model_validator(mode="after")
    def _ordered(self) -> CheckedSlot:
        assert self.end > self.start, "end must follow start"
        return self


class TaggedSlot(BaseModel):
    """A delivery slot whose validator refuses with an error type of its own."""

    start: int
    end: int

    @model_validator(mode="after")
    def _ordered(self) -> TaggedSlot:
        if self.end <= self.start:
            raise PydanticCustomError("slot_order", "end must follow start")
        return self


class Invoice(BaseModel):
    """A field whose type is imported for type checkers only, so pydantic cannot resolve it."""

    lines: Mapping[str, int]


@dataclass
class Parcel:
    """A dataclass with no configuration of its own, for the extra-attributes option."""

    weight: int


@with_config(ConfigDict(extra="forbid"))
@dataclass
class ClosedParcel:
    """A dataclass whose own configuration refuses fields it does not declare."""

    weight: int


class Pickup(BaseModel):
    """One way to hand an order over, told apart from the other by ``kind``."""

    kind: Literal["pickup"]
    store: str


class Delivery(BaseModel):
    """The other way to hand an order over."""

    kind: Literal["delivery"]
    address: str


class Dispatch(BaseModel):
    """A union pydantic picks a member of by the tag the data carries."""

    method: Annotated[Pickup | Delivery, Field(discriminator="kind")]


class Handover(BaseModel):
    """A union pydantic tries member by member."""

    method: Pickup | Delivery


class Letter(BaseModel):
    """Read from the same data as :class:`Packet`, so a union of both takes its first member."""

    weight: int


class Packet(BaseModel):
    """Read from the same data as :class:`Letter`."""

    weight: int
