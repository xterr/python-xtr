# Serialize a class you do not own

A class another library owns, which must stay free of the conversion engine, is made serializable
on the field rather than on the class, with pydantic's own annotations.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, TypeAlias

from pydantic import PlainSerializer, PlainValidator

from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])


class Money:
    """An amount in a currency, owned elsewhere and knowing nothing of this package."""

    def __init__(self, amount: Decimal, currency: str) -> None:
        self.amount = amount
        self.currency = currency

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return (self.amount, self.currency) == (other.amount, other.currency)


def _write_money(money: Money) -> str:
    return f"{money.amount} {money.currency}"


def _read_money(value: object) -> Money:
    if not isinstance(value, str):
        raise ValueError("money is written as text")
    amount, _, currency = value.partition(" ")
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("money is an amount, a space and a three-letter currency")
    return Money(Decimal(amount), currency)


Priced: TypeAlias = Annotated[
    Money, PlainValidator(_read_money), PlainSerializer(_write_money, return_type=str)
]


@dataclass(frozen=True)
class Invoice:
    total: Priced


text = serializer.serialize(Invoice(Money(Decimal("12.50"), "EUR")), "json")
# '{"total":"12.50 EUR"}'

assert serializer.deserialize(text, Invoice, "json") == Invoice(Money(Decimal("12.50"), "EUR"))
```

- **List `PlainValidator` before `PlainSerializer`.** The validator replaces the whole schema the
  annotations before it built, the serializer among them; put it first and the `PlainSerializer`
  after it is kept.
- The reader raises a plain `ValueError` with words that do not quote the value, and it comes back
  as a refusal carrying the field's path.
- The annotation lives on the field, so the class itself stays free of the conversion engine — and
  this works inside a hierarchy's values too.
