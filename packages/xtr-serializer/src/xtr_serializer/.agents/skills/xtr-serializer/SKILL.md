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
  `COLLECT_DENORMALIZATION_ERRORS`, …) — [references/context.md](references/context.md).
- Hierarchies: `@discriminator_map()` on the base, `@discriminator_name("delivery")` on each
  class that is a value of its own. Wire key `"$type"` —
  [references/hierarchies.md](references/hierarchies.md).
- Zone-aware dates: annotate the field `ZonedDateTime`. A plain `datetime` field keeps the offset
  only, and refuses a value in the hour the clocks repeat —
  [references/datetimes.md](references/datetimes.md).
- A class you do not own: `Annotated[T, PlainValidator(read), PlainSerializer(write, return_type=str)]`
  — **validator first**; [references/foreign-types.md](references/foreign-types.md).
- Your own normalizer or encoder:
  [references/normalizers.md](references/normalizers.md).
- In an application, with xtr-dependency-injection installed beside the package, activate
  `SerializerBundle` and inject `SerializerInterface`. Only `xtr_serializer.bundle` needs the
  container; `xtr_serializer.command` needs xtr-console.

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

back = serializer.deserialize(serializer.serialize(mailbox, "json"), Mailbox, "json")
assert back == mailbox
assert type(back.latest) is Delivery
```

`@discriminator_map` goes **after** `@dataclass`, and name every class before a type holding one
is used. The rest — the wire key, intermediate bases, what a forged tag does, a model holding its
own hierarchy — is in [references/hierarchies.md](references/hierarchies.md).

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
3. **Brings along** — the console bundle when xtr-console is installed. The logging bundle, and
   the clock bundle under it, join only when xtr-logging is installed beside them too:
   xtr-console does not depend on it.
4. **Configure** — optional. With nothing configured there is one serializer writing JSON,
   holding the pydantic normalizer, the JSON encoder and every normalizer and encoder **tagged**
   for it — which a class subclassing one of the interfaces is, without being told, while a
   service that only has their methods is not. A default context, named serializers and the tag
   attributes are in [references/application.md](references/application.md).
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
| `PartialDenormalizationError` | `COLLECT_DENORMALIZATION_ERRORS` is on and one or more values did not fit: `errors`, `data` |
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
- Do not expect a service that merely has a normalizer's methods to join a serializer: subclass
  the interface, or tag it where you register it.
- Do not register `Serializer` yourself in a container, or override a built-in normalizer or
  encoder: the bundle's tag attributes are lost. Configure through `SerializerConfig` and the
  tags.
- Do not feed untrusted data of unbounded size to the decoder before capping the request:
  crafted sets and integer-keyed dicts are quadratic.
