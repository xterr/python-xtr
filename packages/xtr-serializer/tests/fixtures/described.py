"""Classes ``debug:serializer`` describes: a dataclass, a model renaming its fields, and others."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Account", "Empty", "Shipment", "Untyped", "not_a_class"]


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
