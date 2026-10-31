"""Messages whose ``repr`` does not tell them apart, or differs from one process to the next."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from pydantic import BaseModel
from pydantic_core import core_schema
from typing_extensions import override
from xtr_messenger import as_message

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler

#: Resources whose names a set hands out in an order that changes with the hash seed.
RESOURCES = frozenset({"cpu", "memory", "disk", "network", "gpu", "storage", "requests"})


@as_message(name="probe.quotas.v1")
@dataclass(frozen=True)
class Quotas:
    """A dict whose key order, and so its ``repr``, follows the set it was built from."""

    limits: dict[str, int]


@final
class Sku:
    """A value object with no ``repr`` of its own: the default one shows its address."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code

    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Sku) and other.code == self.code

    @override
    def __hash__(self) -> int:
        return hash(self.code)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: object, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        del source, handler
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(cls, core_schema.str_schema()),
            python_schema=core_schema.is_instance_schema(cls),
            serialization=core_schema.plain_serializer_function_ser_schema(
                _code, return_schema=core_schema.str_schema()
            ),
        )


def _code(sku: Sku) -> str:
    return sku.code


class Restock(BaseModel):
    """A model holding a value object whose ``repr`` is its address."""

    sku: Sku
    quantity: int


@dataclass(frozen=True)
class RotateToken:
    """A message keeping its secret out of its ``repr``."""

    tenant: str
    token: str = field(repr=False)


def quotas() -> Quotas:
    """Return quotas built by walking a set, as an application might."""
    return Quotas({name: len(name) for name in set(RESOURCES)})


def restock() -> Restock:
    """Return a restock of a fresh value object."""
    return Restock(sku=Sku("A-17"), quantity=3)
