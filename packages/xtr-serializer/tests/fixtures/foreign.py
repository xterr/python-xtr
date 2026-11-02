"""A class that knows nothing of pydantic, carried by fields annotated with how to write it."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Annotated, TypeAlias, final

from pydantic import PlainSerializer, PlainValidator
from typing_extensions import override

from xtr_serializer import discriminator_map, discriminator_name

__all__ = ["Bill", "Charge", "Fee", "Money", "Priced"]


@final
class Money:
    """An amount in a currency: a class of another library, which must stay free of pydantic."""

    __slots__ = ("amount", "currency")

    def __init__(self, amount: Decimal, currency: str) -> None:
        self.amount = amount
        self.currency = currency

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return (type(self.amount), self.amount, self.currency) == (
            type(other.amount),
            other.amount,
            other.currency,
        )

    @override
    def __hash__(self) -> int:
        return hash((self.amount, self.currency))


def _write(money: Money) -> str:
    return f"{money.amount} {money.currency}"


def _read(value: object) -> Money:
    """Read ``"<amount> <currency>"``, refusing in words that do not quote the value."""
    if not isinstance(value, str):
        msg = "money is written as text"
        raise ValueError(msg)  # noqa: TRY004 - pydantic reports a ValueError as a validation error
    amount, _, currency = value.partition(" ")
    try:
        number = Decimal(amount)
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite() or len(currency) != 3 or not currency.isalpha():
        msg = "money is an amount, a space and a three-letter currency"
        raise ValueError(msg)
    return Money(number, currency)


Priced: TypeAlias = Annotated[
    Money, PlainValidator(_read), PlainSerializer(_write, return_type=str)
]
"""A field holding money: the annotation, not the class, says how it is written and read.

The validator comes first: it replaces the whole schema, and the serializer after it is kept.
"""


@discriminator_map()
@dataclass(frozen=True)
class Charge:
    """The base of a hierarchy whose classes hold money."""

    label: str


@discriminator_name("fee")
@dataclass(frozen=True)
class Fee(Charge):
    price: Priced


@dataclass(frozen=True)
class Bill:
    """Money in a field of its own and inside the values of a hierarchy."""

    total: Priced
    charges: list[Charge] = field(default_factory=list[Charge])
