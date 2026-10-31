---
name: xtr-serializer
description: How to write values as JSON and read them back exactly with xtr-serializer — a Serializer over normalizers and encoders, declared types, class hierarchies tagged on the wire, zone-aware datetimes, and refusals that never quote the input. Use when code must put a dataclass or model on a wire or in storage and get the same value back, when a subclass in a field typed with its base loses its fields, when a tuple, Decimal, UUID, bytes or datetime changes across a round trip, when a datetime must keep its zone name, when a class another library owns must be serializable, when writing a normalizer or an encoder of your own, when adding SerializerBundle or named serializers to an application on xtr-dependency-injection, or when reading debug:serializer.
---

# xtr-serializer

A `Serializer` is a list of normalizers (object ⇄ plain data) and a list of encoders (plain data
⇄ text). pydantic does the conversion. What this package adds is the chain, the context, the
errors, the bundle — and one promise: a value is written, read back under the same options and
compared, so what comes back equals what went in, or the write is **refused** with the path to
the value that would have changed.

Everything is judged against the **declared** type, not the runtime one.

## Quick reference

- Build one: `serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])`. Priority is list
  order; put a narrow normalizer before `PydanticNormalizer`, which handles nearly anything.
- Write and read: `serializer.serialize(value, "json")` → `str`;
  `serializer.deserialize(text, Order, "json")` → `Order`. `deserialize` takes `str` or `bytes`.
- A bare `list`/`dict` declares nothing about its items: pass
  `serialize(items, "json", type_=list[Order])` and `deserialize(text, list[Order], "json")`.
  Without `type_`, a container is accepted only while everything in it is plain JSON already.
- Steps on their own: `normalize`, `denormalize`, `encode`, `decode`.
- Options go in a context mapping, built by `SerializerContextBuilder`,
  `PydanticNormalizerContextBuilder`, `JsonEncoderContextBuilder`, or written by hand with the
  public key constants (`STRICT`, `BY_ALIAS`, `ALLOW_EXTRA_ATTRIBUTES`, `JSON_INDENT`,
  `COLLECT_DENORMALIZATION_ERRORS`, …). A call's context wins over the serializer's
  `default_context` key by key.
- Hierarchies: `@discriminator_map()` on the base, `@discriminator_name("delivery")` on each
  class that is a value of its own. Wire key `"$type"`.
- Zone-aware dates: annotate the field `ZonedDateTime`. A plain `datetime` field keeps the offset
  only.
- A class you do not own: `Annotated[T, PlainValidator(read), PlainSerializer(write, return_type=str)]`
  — **validator first**.
- In an application, with xtr-dependency-injection installed beside the package, activate
  `SerializerBundle` and inject `SerializerInterface`. Only `xtr_serializer.bundle` and
  `xtr_serializer.command` need the container.

## Round-trip a value

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer


@dataclass(frozen=True)
class Order:
    reference: str
    total: Decimal
    placed_at: datetime


serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])

order = Order("A-17", Decimal("19.99"), datetime(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("UTC")))
text = serializer.serialize(order, "json")
# '{"reference":"A-17","total":"19.99","placed_at":"2026-03-01T09:30:00Z"}'

assert serializer.deserialize(text, Order, "json") == order
```

`Decimal`, `UUID`, `bytes` (base64url), `date`, `time`, `timedelta`, `Path`, enums, tuples, sets
and frozensets all come back by their declared type. A naive datetime in a plain `datetime` field
is refused — aware only.

## Set options for a call

```python
from xtr_serializer import JsonEncoderContextBuilder, PydanticNormalizerContextBuilder

context = (
    PydanticNormalizerContextBuilder(JsonEncoderContextBuilder().with_indent(2).to_dict())
    .with_ignored_attributes({"total"})
    .to_dict()
)
# {'json_indent': 2, 'ignored_attributes': frozenset({'total'})}

serializer.serialize(order, "json", context)
# '{\n  "reference": "A-17",\n  "placed_at": "2026-03-01T09:30:00Z"\n}'
```

Builders are immutable — each `with_*` returns a new one — and each sets only its own step's
keys, so they chain by handing one's `to_dict()` to the next. The whole context also reaches
pydantic as `info.context`, so an application's validators read it.

Leaving fields out (`with_attributes`, `with_ignored_attributes`, the `skip_*` options) is a
partial write: it is checked, but not read back, so the exactness promise does not apply to it.

## Keep a datetime's zone

```python
from xtr_serializer import ZonedDateTime


@dataclass(frozen=True)
class Reminder:
    at: ZonedDateTime


repeated = datetime(2026, 10, 25, 3, 30, tzinfo=ZoneInfo("Europe/Bucharest"), fold=1)

text = serializer.serialize(Reminder(repeated), "json")
# '{"at":"2026-10-25T03:30:00+02:00[Europe/Bucharest]"}'

read = serializer.deserialize(text, Reminder, "json")
assert read.at == repeated
assert (read.at.tzinfo, read.at.fold) == (ZoneInfo("Europe/Bucharest"), 1)
```

The same value in a plain `datetime` field is refused when it is written: in the hour the clocks
repeat the offset alone cannot tell the two 03:30s apart. `ZonedDateTime` refuses a naive
datetime, a fixed offset and a zone with no name; reading refuses text not in that form, an
unknown zone, and an offset the zone does not have at that time.

## Carry a class hierarchy

```python
from dataclasses import dataclass, field

from xtr_serializer import discriminator_map, discriminator_name


@discriminator_map()
@dataclass(frozen=True)
class Event:
    name: str


@discriminator_name("delivery")
@dataclass(frozen=True)
class Delivery(Event):
    recipient: str


@dataclass(frozen=True)
class Mailbox:
    latest: Event
    history: list[Event] = field(default_factory=list[Event])


mailbox = Mailbox(Delivery("sent", "ana@example.com"), [Delivery("sent", "bo@example.com")])

text = serializer.serialize(mailbox, "json")
# '{"latest":{"$type":"delivery","name":"sent","recipient":"ana@example.com"},
#   "history":[{"$type":"delivery","name":"sent","recipient":"bo@example.com"}]}'

back = serializer.deserialize(text, Mailbox, "json")
assert back == mailbox
assert type(back.latest) is Delivery
```

- `@discriminator_map` goes **after** `@dataclass`, and **before** `@discriminator_name` when the
  base has a name of its own.
- Name every class before a type holding one is used — and before a model holding one is defined,
  as a model builds its schema then. A model holding its own hierarchy needs
  `model_config = ConfigDict(defer_build=True)`.
- A tag is looked up among the registered subclasses of the declared type only, so an unknown,
  forged or missing tag is refused:

  ```python
  serializer.deserialize('{"latest": {"$type": "nowhere", "name": "sent"}}', Mailbox, "json")
  # NotNormalizableValueError: at 'latest': the data must be an object whose '$type' names a
  # class the declared type takes (got 'dict')
  ```
- A value of an unnamed subclass is refused rather than written as its base. Name even a subclass
  that adds no field.
- `@discriminator_map("kind")` picks another key, which must be no field's name or alias.
  Dataclasses, pydantic dataclasses and models all work; a generic class cannot be in a
  hierarchy.

## Serialize a class you do not own

```python
from typing import Annotated, TypeAlias

from pydantic import PlainSerializer, PlainValidator

Priced: TypeAlias = Annotated[
    Money, PlainValidator(_read_money), PlainSerializer(_write_money, return_type=str)
]


@dataclass(frozen=True)
class Invoice:
    total: Priced


text = serializer.serialize(Invoice(Money(Decimal("12.50"), "EUR")), "json")
# '{"total":"12.50 EUR"}'
```

**List `PlainValidator` before `PlainSerializer`.** The validator replaces the whole schema the
annotations before it built, the serializer included; put it first and the serializer after it is
kept. The reader raises a plain `ValueError` whose words do not quote the value, and it comes
back as a refusal carrying the field's path. The annotation lives on the field, so the class
itself stays free of the conversion engine — and works inside a hierarchy's values too.

## Write a normalizer or an encoder

```python
from xtr_serializer import NotNormalizableValueError


class PointNormalizer:
    """Writes a point as a pair of numbers, and reads that pair back into a point."""

    def normalize(self, data, format=None, context=None, *, type_=None):
        if not isinstance(data, Point):
            raise NotNormalizableValueError("only a point is written here")
        return [data.x, data.y]

    def supports_normalization(self, data, format=None, context=None, *, type_=None):
        return isinstance(data, Point)

    def denormalize(self, data, type_, format=None, context=None):
        match data:
            case [int() as x, int() as y] if type_ is Point:
                return Point(x, y)
            case _:
                raise NotNormalizableValueError(
                    "a point is a pair of whole numbers",
                    expected_types=("Point",),
                    current_type=type(data).__name__,
                )

    def supports_denormalization(self, data, type_, format=None, context=None):
        return type_ is Point

    def get_supported_types(self, format):
        return {Point: True}


serializer = Serializer([PointNormalizer(), PydanticNormalizer()], [JsonEncoder()])
serializer.serialize(Point(3, 4), "json")  # '[3,4]'
```

- The interfaces — `NormalizerInterface`, `DenormalizerInterface`, `EncoderInterface`,
  `DecoderInterface` — are `Protocol`s, so the methods are what counts. `normalize` and
  `supports_normalization` must accept the keyword-only `type_`.
- `get_supported_types(format)` keys are a class (standing for its subclasses), `"object"` (every
  class) or `"*"` (anything, `int | None` included); the value is `True` when the answer rests on
  the type and format alone (asked once and remembered), `False` when the value or context
  matters, `None` for a type you do not handle. List narrower class keys first.
- Take `SerializerAwareInterface`, `NormalizerAwareInterface` or `DenormalizerAwareInterface` and
  the serializer hands itself over for nested values.
- An encoder implements `encode`, `supports_encoding`, `decode`, `supports_decoding`, and a
  format string of its own.

## Testing

- Use a real serializer; there is nothing to mock. `Serializer([PydanticNormalizer()],
  [JsonEncoder()])` touches no I/O.
- Assert the round trip, and the exact type of every nested value — equality alone would pass for
  a subclass written as its base:

  ```python
  def test_a_delivery_in_an_event_field_comes_back_a_delivery() -> None:
      serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
      mailbox = Mailbox(Delivery("sent", "ana@example.com"))

      back = serializer.deserialize(serializer.serialize(mailbox, "json"), Mailbox, "json")

      assert back == mailbox
      assert type(back.latest) is Delivery
  ```

- Assert refusals by type and path, never by the whole message:

  ```python
  import pytest
  from xtr_serializer import NotNormalizableValueError


  def test_a_forged_tag_is_refused() -> None:
      with pytest.raises(NotNormalizableValueError) as raised:
          serializer.deserialize('{"latest": {"$type": "nowhere"}}', Mailbox, "json")

      assert raised.value.path == "latest"
  ```

- Name the hierarchy's classes at module level in the test module or a fixtures module, before
  any type holding them is used. A name cannot be added once a schema covering the base is built,
  and the registry lives for the process — so never register names inside a test body.
- With a kernel, `assert_zero_config(SerializerBundle)` is the bundle's own contract test, and
  `boot_for_test(kernel, overrides={SerializerInterface: ...})` swaps the serializer out.
- Freeze a clock with `xtr-clock`'s `mock_time` when the value under test carries a date it
  reads.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`SerializerBundle`. There is no config file, environment or ignore line to write; the steps below
that it cannot make, it prints.

1. **Install** — `uv add xtr-serializer xtr-dependency-injection`: the bundle needs the container
   installed beside it, never as an extra. Install xtr-console beside it for `debug:serializer`.
2. **Activate** — `SerializerBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
   imported from `xtr_serializer.bundle`.
3. **Brings along** — the console bundle when xtr-console is installed, and through it the
   logging bundle and its clock.
4. **Configure** — optional. With nothing configured there is one serializer writing JSON,
   holding the pydantic normalizer, the JSON encoder and every normalizer and encoder the
   application registers:

   ```python
   # <app>/config/packages/serializer.py
   from xtr_dependency_injection import configure
   from xtr_serializer import SKIP_NULL_VALUES, STRICT
   from xtr_serializer.bundle import NamedSerializerConfig, SerializerConfig


   @configure
   def serializer() -> SerializerConfig:
       return SerializerConfig(
           default_context={STRICT: True},
           named_serializers={"api": NamedSerializerConfig(default_context={SKIP_NULL_VALUES: True})},
       )
   ```

   `NamedSerializerConfig` also takes `include_built_in_normalizers` and
   `include_built_in_encoders`; `False` leaves the built-in one out, and the serializer must then
   be given one by a tag. `"default"` and `"*"` are reserved names.
5. **Environment** — nothing is read from the environment. A value given as `env(...)` in a
   configured default context must be set at boot, which builds every serializer.
6. **Ignore** — nothing: the serializer writes no file into the project.
7. **Use** — inject the interface; the default serializer has no qualifier, a named one is
   reached by its name:

   ```python
   from typing import Annotated

   from xtr_dependency_injection import Target, as_service
   from xtr_serializer import SerializerInterface


   @as_service
   class Outbox:
       def __init__(
           self,
           serializer: SerializerInterface,
           api: Annotated[SerializerInterface, Target("api")],
       ) -> None: ...
   ```

   Every serializer is registered under `SerializerInterface`, `NormalizerInterface`,
   `DenormalizerInterface`, `EncoderInterface` and `DecoderInterface`. A normalizer or encoder
   class joins the default serializer by subclassing an interface; tag it to place it:
   `services.set(MoneyNormalizer).add_tag(NORMALIZER_TAG, priority=10, serializer="*")`.
8. **Check** — `debug:bundles` shows `serializer` as `listed` and `active`.
   `debug:serializer <module:Class>` shows the class's fields as it is read (`validation`) and as
   it is written (`serialization`), and the classes of its hierarchy.
9. **Remove** — drop the `BUNDLES` entry (`uv run xtr-recipes recipes:remove xtr-serializer`),
   delete `<app>/config/packages/serializer.py` if you wrote one, then `uv remove xtr-serializer`.

## Errors

Every error derives from `SerializerError`. None repeats a value it was handed: a message says
where the problem is and which types were involved.

| Error | Raised when |
| --- | --- |
| `NotNormalizableValueError` | A value has no exact plain form, or data does not fit the declared type. `path`, `expected_types`, `current_type`, `error_type` |
| `ExtraAttributesError` | Data carried fields its type does not declare, with `ALLOW_EXTRA_ATTRIBUTES` off. A `NotNormalizableValueError`, with `extra_attributes` |
| `PartialDenormalizationError` | `COLLECT_DENORMALIZATION_ERRORS` is on and several values did not fit: `errors`, `data` |
| `NotEncodableValueError` | Plain data has no form in the format, or the text is not valid in it |
| `UnsupportedFormatError` | Nothing writes or reads the format asked for. A `NotEncodableValueError`, with `format` |
| `CircularReferenceError` | A value contains itself. Also a `RuntimeError` |
| `MappingError` | A hierarchy registered in a way that cannot work — duplicate name, class in no hierarchy, key a field also uses. A `LogicError`, raised at registration |
| `LogicError` | The serializer was put together in a way no input could make right. Also a `RuntimeError` |
| `InvalidArgumentError` | An argument or a configuration cannot be used. Also a `ValueError` |

Raise these with their typed fields and **no `from` clause**: chaining an exception that carries
the value puts that value in the traceback.

## Do not

- Do not expect a bare `list` or `dict` of objects to be written. Pass `type_=list[Order]`, or it
  is refused.
- Do not rely on a subclass surviving a field typed with its base without a hierarchy. Declare
  `@discriminator_map()` and name the classes.
- Do not register a `@discriminator_name` lazily — in a function, a test body, or after a type
  holding the class has been used. It raises `MappingError`.
- Do not use an import path, a class name or a module path as a wire tag. Only registered names
  are read, and that is the point.
- Do not put `PlainSerializer` before `PlainValidator` in an `Annotated`. The validator throws
  the serializer away.
- Do not store a `ZoneInfo` datetime in a plain `datetime` field and expect the zone back. Use
  `ZonedDateTime`, or store UTC.
- Do not pass a generator or a one-shot iterator as `normalizers` or `encoders`: the serializer
  ends up empty.
- Do not mutate the mapping a serializer was built with as its `default_context`, nor the context
  a normalizer is handed — with no call context, every call gets the serializer's own.
- Do not put a value in an error message, and do not `raise ... from` an exception holding the
  input.
- Do not register `Serializer` yourself in a container, or override a built-in normalizer or
  encoder: the bundle's tag attributes are lost. Configure through `SerializerConfig` and the
  tags.
- Do not feed untrusted data of unbounded size to the decoder before capping the request:
  crafted sets and integer-keyed dicts are quadratic.
