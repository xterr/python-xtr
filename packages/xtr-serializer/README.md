<div align="center">

# xtr-serializer

**Turn objects into JSON and back exactly — dataclasses, models, class hierarchies and dates arrive as they left, or are refused — through a chain of normalizers and encoders.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Putting a value on a wire and taking it back is where types quietly go missing. A tuple comes
back a list, a `Decimal` a float, a subclass in a field typed with its base comes back as the
base with its own fields dropped — and nothing says so. The value is simply not the value any
more, three services downstream.

This package puts one `SerializerInterface` in front of a chain of **normalizers** (object ⇄
plain data) and **encoders** (plain data ⇄ text). pydantic does the reading and the writing; what
this adds is the shape around it and one promise:

- 🎯 **Exact round trips** — what is read back equals what was written, and every nested value
  has the type its annotation declares. The check is real: a value is written, read back under
  the same options, and compared. A value that would come back changed is **refused when it is
  written**, with the path to it.
- 🧬 **Class hierarchies** — a base declares itself with `@discriminator_map()`, each class in it
  registers a wire name with `@discriminator_name("delivery")`, and a field typed with the base
  carries any of them, nested, in lists, in dicts. Only registered names are read, never an
  import path from the data.
- 🕰️ **Zone-aware datetimes** — `ZonedDateTime` keeps the zone's name and the `fold`, so even the
  hour the clocks repeat comes back equal.
- 🔒 **Errors that never quote the input** — a refusal says where the value sits and which types
  were involved. What goes through a serializer is often a password or a token.
- 🧩 **An optional bundle** — serializers configured in Python, named ones for parts of the
  application that write differently, and `debug:serializer` once xtr-dependency-injection and
  xtr-console are installed beside it.

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

## Install

```sh
uv add xtr-serializer
uv add xtr-serializer xtr-dependency-injection  # + the container, for the SerializerBundle
uv add xtr-console                              # beside it: debug:serializer
```

Requires Python 3.11+. Depends on `pydantic` and `typing-extensions` — not on the container: the
bundle is used when xtr-dependency-injection is installed beside the package, and nothing outside
`xtr_serializer.bundle` and `xtr_serializer.command` needs it.

## Quick start

A serializer is a list of normalizers and a list of encoders, each in the order it tries them:

```python
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
```

`serialize` writes a value as text, `deserialize` reads text back into the type asked for:

```python
text = serializer.serialize(order, "json")
order = serializer.deserialize(text, Order, "json")
```

What is written follows from the type the value is **declared** with — its own class unless
`type_` says otherwise. A bare list or dict declares nothing about what it holds, so say what it
holds:

```python
text = serializer.serialize([order], "json", type_=list[Order])
# '[{"reference":"A-17","total":"19.99","placed_at":"2026-03-01T09:30:00Z"}]'

orders = serializer.deserialize(text, list[Order], "json")
```

Written without `type_`, a list or a dict is accepted only while everything in it is plain JSON
already — a number, a string, `True`, `None`, or lists and dicts of those. Anything else is
refused rather than written as something that would read back changed.

`normalize`, `denormalize`, `encode` and `decode` are on the serializer too, for the steps on
their own: plain data without text, or text without objects.

## Options: the context

Every call takes a context — a plain mapping each step reads its own keys from. A builder per
step sets them with typed methods, and each builder leaves the other steps' keys alone, so they
chain:

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

Builders are immutable: setting an option returns a new builder, so one holding an application's
defaults can be extended for a single call. A serializer built with `default_context=` starts
every call from those options, and a call's context wins over them key by key.

| Builder | Sets |
|---|---|
| `SerializerContextBuilder` | `with_collect_denormalization_errors` |
| `PydanticNormalizerContextBuilder` | `with_attributes`, `with_ignored_attributes`, `with_skip_null_values`, `with_skip_unset_values`, `with_skip_default_values`, `with_by_alias`, `with_strict`, `with_allow_extra_attributes`, `with_from_attributes`, `with_populate_by_name` |
| `JsonEncoderContextBuilder` | `with_indent` |

Each key is a public constant with the same name in upper case — `STRICT`, `BY_ALIAS`,
`JSON_INDENT`, `COLLECT_DENORMALIZATION_ERRORS` — for a context written by hand. The context is
also handed to pydantic as `info.context`, so an application's own validators read it.

## Dates that keep their zone

A plain `datetime` field writes an aware datetime with its offset and reads it back with that
offset: the same instant, but the zone's name is gone — and a value in the hour the clocks
repeat is refused when it is written, since the offset alone cannot tell the two 03:30s apart.
Annotate the field `ZonedDateTime` and the name and the `fold` both survive:

```python
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

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

One string, the form RFC 9557 gives: the ISO datetime with its offset, then the zone's name. The
same value in a plain `datetime` field is refused when it is written, naming the field.

`date`, `time`, `timedelta`, `Decimal`, `UUID`, `bytes` (base64url), `Path`, enums, tuples,
frozensets and sets all round-trip by their declared type, with no annotation.

## Class hierarchies

A field typed with a base class holds a value of any subclass. Declare the hierarchy once on the
base, and name each class that is a value of its own:

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
```

```python
mailbox = Mailbox(Delivery("sent", "ana@example.com"), [Delivery("sent", "bo@example.com")])

text = serializer.serialize(mailbox, "json")
# '{"latest":{"$type":"delivery","name":"sent","recipient":"ana@example.com"},
#   "history":[{"$type":"delivery","name":"sent","recipient":"bo@example.com"}]}'

back = serializer.deserialize(text, Mailbox, "json")
assert back == mailbox
assert type(back.latest) is Delivery
```

- The wire key is `"$type"` by default — no name a field can have. `@discriminator_map("kind")`
  picks another, which must be no field's name or alias.
- A name is the data's word for the class: choose one that stays when the class moves or is
  renamed. Only a named class is written; a value of an unnamed subclass is refused rather than
  written as its base.
- A tag is resolved among the registered subclasses **of the declared type only**, so data cannot
  name a class of another hierarchy or one the field does not take. An unknown, forged or missing
  tag is refused:

  ```python
  serializer.deserialize('{"latest": {"$type": "nowhere", "name": "sent"}}', Mailbox, "json")
  # NotNormalizableValueError: at 'latest': the data must be an object whose '$type' names a
  # class the declared type takes (got 'dict')
  ```
- Dataclasses, pydantic dataclasses and models all work, as do intermediate bases: a field typed
  with one takes the named classes under it.
- Apply `@discriminator_map` after `@dataclass`, and before `@discriminator_name` when the base
  has a name of its own. Name every class of a hierarchy before a type holding one is used — the
  schema built for that type keeps the names it found.

## Types from elsewhere

A class another library owns, which must stay free of the conversion engine, is made serializable
on the field rather than on the class, with pydantic's own annotations:

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, TypeAlias

from pydantic import PlainSerializer, PlainValidator


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

**List the validator before the serializer.** `PlainValidator` replaces the whole schema the
annotations before it built, the serializer among them; put it first and the `PlainSerializer`
after it is kept. The reader raises a plain `ValueError` with words that do not quote the value,
and it comes back as a refusal with the field's path. This works inside a hierarchy's values too.

## Normalizers and encoders of your own

A normalizer handles the types it reports and leaves the rest; the serializer gives each value to
the first one that handles it, in the order the list has them. Put yours before the pydantic
normalizer, which handles nearly anything:

```python
from dataclasses import dataclass

from xtr_serializer import NotNormalizableValueError


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


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

- Implement `NormalizerInterface`, `DenormalizerInterface` or both; an encoder implements
  `EncoderInterface`, `DecoderInterface` or both. They are `Protocol`s — subclassing is optional,
  the methods are what counts, and `normalize` / `supports_normalization` must accept the
  keyword-only `type_`.
- `get_supported_types(format)` is how a serializer skips you without asking: a key is a class
  (standing for its subclasses), `"object"` (every class) or `"*"` (anything at all, type
  expressions such as `int | None` included). Its value is `True` when the answer rests on the
  type and the format alone — asked once per type and remembered — `False` when it rests on the
  value or the context too, and `None` for a type you do not handle.
- **Priority is list order**, both in code and, through the bundle, by the tag's `priority`
  attribute, highest first.
- Take `SerializerAwareInterface`, `NormalizerAwareInterface` or `DenormalizerAwareInterface` and
  the serializer hands itself over, for values nested inside yours.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-serializer xtr-dependency-injection`: the bundle needs the container
  installed beside it, never as an extra. Install xtr-console beside it for `debug:serializer`.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `SerializerBundle`. There is no config file, environment or ignore line to write.
- **Activate** — `SerializerBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_serializer.bundle`.
- **Brings along** — the console bundle, when xtr-console is installed; in debug mode that is
  where `debug:serializer` comes from. The logging bundle, and the clock bundle under it, join
  only when xtr-logging is installed beside them too: xtr-console does not depend on it.
- **Configure** — optional: with no configuration there is one serializer writing JSON, holding
  the pydantic normalizer, the JSON encoder and every normalizer and encoder **tagged** for it.
  A class subclassing `NormalizerInterface`, `DenormalizerInterface`, `EncoderInterface` or
  `DecoderInterface` is tagged without being told; a service that only has their methods is not,
  and joins nothing until a tag puts it there. Options every call starts from, and serializers
  besides the default one, go in a `<app>/config/packages/serializer.py` `@configure` function
  returning `SerializerConfig` — see [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing read from the environment. A value given as `env(...)` in a
  configured default context must be set when the application boots: booting builds every
  serializer.
- **Ignore** — nothing: the serializer writes no file into the project.
- **Remove** — drop the `BUNDLES` entry (`uv run xtr-recipes recipes:remove xtr-serializer` does
  it, and there is no file of its own to take away), delete
  `<app>/config/packages/serializer.py` if you wrote one, then `uv remove xtr-serializer`.
- **Check** — `debug:bundles` shows `serializer` as `listed` and `active`;
  `debug:serializer <module:Class>` shows how that class is read and written.

## Kernel / bundle

With [xtr-dependency-injection](../xtr-dependency-injection) installed beside the package, list
the bundle:

```python
# app/config/bundles.py
from xtr_serializer.bundle import SerializerBundle

BUNDLES = {SerializerBundle: {"all": True}}
```

The default serializer is then registered under `SerializerInterface`, `NormalizerInterface`,
`DenormalizerInterface`, `EncoderInterface` and `DecoderInterface`, with no qualifier:

```python
from xtr_dependency_injection import as_service
from xtr_serializer import SerializerInterface


@as_service
class Outbox:
    def __init__(self, serializer: SerializerInterface) -> None: ...
```

Configuring is optional. A default context, and serializers for parts of the application that
write differently, go in one function:

```python
# app/config/packages/serializer.py
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

| `SerializerConfig` field | Meaning |
|---|---|
| `default_context` | Options every call to every serializer starts from; a call's context wins over them key by key |
| `named_serializers` | Serializers besides the default one, each registered under its name as the qualifier. `"default"` and `"*"` are the names tags use, so neither names one here |

| `NamedSerializerConfig` field | Meaning |
|---|---|
| `default_context` | Options every call to it starts from, over the bundle's own key by key |
| `include_built_in_normalizers` | Whether the bundle's own pydantic normalizer joins it. `False` and the serializer has only what is tagged for it, and must be given one |
| `include_built_in_encoders` | The same for the JSON encoder |

A named serializer is injected by its name:

```python
from typing import Annotated

from xtr_dependency_injection import Target
from xtr_serializer import SerializerInterface

api: Annotated[SerializerInterface, Target("api")]
```

- **Tags**: a service joins a serializer by `NORMALIZER_TAG` (`"serializer.normalizer"`) or
  `ENCODER_TAG` (`"serializer.encoder"`). Three optional attributes:

  | Attribute | Means |
  |---|---|
  | `priority` | An `int`, higher tried first; without it, the definition's own priority, or 0 |
  | `serializer` | The name it joins, or a sequence of names: `"default"` (the default when absent), a configured name, or `"*"` for every serializer |
  | `built_in` | `True` for one a named serializer can leave out |

  ```python
  from xtr_serializer.bundle import NORMALIZER_TAG


  def load_extension(self, config, services, builder) -> None:
      _ = services.set(PointNormalizer).add_tag(NORMALIZER_TAG, priority=10, serializer="*")
  ```

  A class subclassing one of the interfaces carries the tag without being told, with no
  attribute — which puts it in the default serializer at its definition's own priority. A
  service that merely has a normalizer's or an encoder's methods carries nothing, and a
  serializer holds only what is tagged: tag it where you register it.
- **Zero config**: one serializer writing JSON. Nothing is converted until something asks for one.
- **Checked at build**: a tag that cannot be read, one naming a serializer that does not exist,
  and a serializer left without a normalizer or an encoder all fail the build. Booting then
  builds every serializer, so a service tagged as what it is not fails there rather than on the
  first call.
- **Named copies**: each named serializer gets its own instance of every service it shares with
  another, under the key `serializer.<name>[.<qualifier>]` — a service is handed the serializer
  holding it, and one instance can only be handed one.
- **Console**: in debug mode, with a console bundle active, `debug:serializer` is registered.

## Console commands

| Command | Does |
|---|---|
| `debug:serializer CLASS` | Shows the fields of `module:Class` as it is read and as it is written, and the classes of its hierarchy |

```
$ debug:serializer mailroom:Event

mailroom.Event
==============

  [NOTE] It has no name in its hierarchy, so it is never written itself: a value of it is one of
  the classes below.

discriminator map
-----------------

Type property: $type
┌──────────┬───────────────────┐
│ Name     │ Class             │
├──────────┼───────────────────┤
│ delivery │ mailroom.Delivery │
└──────────┴───────────────────┘
```

`validation` is how data is read into the class, `serialization` how a value of it is written.

## Errors

Every error derives from `SerializerError`, so one `except` at the edge answers for all of them.
No error repeats a value it was handed: a message says where the problem is and which types were
involved, never what the value was.

| Error | Raised when |
|---|---|
| `SerializerError` | The base; catch it to catch them all |
| `UnexpectedValueError` | The family about the data itself. Also a `ValueError` |
| `NotNormalizableValueError` | A value has no exact plain form, or data does not fit the declared type. Carries `path`, `expected_types`, `current_type`, `error_type` |
| `ExtraAttributesError` | Data carried fields its type does not declare, and they are refused rather than dropped. A `NotNormalizableValueError`, with `extra_attributes` |
| `PartialDenormalizationError` | `COLLECT_DENORMALIZATION_ERRORS` is on and one or more values did not fit: `errors` holds one per value, `data` what was read |
| `NotEncodableValueError` | Plain data has no form in the format — a float infinity — or the text is not valid in it |
| `UnsupportedFormatError` | Nothing in the serializer writes or reads the format asked for. A `NotEncodableValueError`, with `format` |
| `CircularReferenceError` | A value contains itself. Also a `RuntimeError` |
| `LogicError` | The serializer was put together in a way no input could make right. Also a `RuntimeError` |
| `MappingError` | A class hierarchy was registered in a way that cannot work — a duplicate name, a name on a class in no hierarchy, a key a field also uses. A `LogicError`, raised where the classes are registered |
| `InvalidArgumentError` | An argument or a configuration cannot be used, whatever data comes next. Also a `ValueError` |

```python
serializer.deserialize('{"reference": "A-17", "total": "many"}', Order, "json")
# NotNormalizableValueError: at 'total': Input should be a valid decimal (got 'str')
```

A message stays free of the value only while callers keep the value out of the chain: an error
raised *from* an exception carrying the value puts it in the traceback. Raise these errors with
their typed fields and no `from` clause.

## Known limitations

### Reading and writing

- A `ZoneInfo` datetime in a plain `datetime` field keeps only its offset, and in a repeated or
  skipped hour it is refused — annotate it `ZonedDateTime`, or store UTC. An aware datetime reads
  back with pydantic's own `TzInfo`: equal, not the same tzinfo object or class.
- Each unknown zone name in a `ZonedDateTime` is looked up on disk.
- A plain `datetime` field reads a string of digits as a Unix timestamp in UTC.
- A `ZonedDateTime` is read by Python's ISO parser, so ISO week dates are accepted; on a
  case-insensitive filesystem a zone name in another case is read as spelled.
- With pydantic before 2.14, a `NamedTuple`'s items are written by their runtime type, so a
  `ZonedDateTime` or a hierarchy value inside one is refused.
- `denormalize` reads its data as JSON: Python `set`, `tuple`, `bytes`, `UUID` and `Decimal`
  objects are taken in their JSON form. Extra fields are dropped unless
  `ALLOW_EXTRA_ATTRIBUTES` is off, and among duplicate keys the last wins.
- A `Decimal` field given a JSON *number* gets float precision; a string keeps every digit. More
  than six fractional-second digits in a datetime are truncated.
- Refused because pydantic does not write them back: private attributes and `Field(exclude=True)`
  holding a non-default value, computed fields under `extra="forbid"`, dicts with tuple keys,
  integers over 4300 digits, and a field whose `validation_alias` differs from its
  `serialization_alias` — the refusal does not name the alias mismatch. A partial write — one
  leaving fields out through `ATTRIBUTES`, `IGNORED_ATTRIBUTES` or the `skip_*` options — is
  checked but not read back.
- `Serializer` does not look inside a bare list or dict: it goes to a normalizer whole, and a
  custom normalizer is never handed a container's items. Primitives skip the normalizers only
  when writing — a serializer with no denormalizer refuses `deserialize("5", int, "json")`.
- In `get_supported_types`, a key naming the type itself counts first, so `None` there settles
  it; failing that, the first class key covering the type, in the order reported, counts — so
  list narrower keys first. A class key never covers `list[Point]` or `Point | None` — only
  `"*"` does.
- Which normalizer handles a type is kept per format, for the 256 types used last; the pydantic
  normalizer keeps the adapters it builds for the 256 types used last, whatever the format, as
  they do not depend on one. More types than that, or an `Annotated[...]` built per call, are
  rebuilt every time. A type whose own code raises when it is hashed or compared is never kept.
- `normalizers` and `encoders` must be sequences: a one-shot iterator leaves the serializer
  empty. With no call context, every call is handed the serializer's own default context —
  copy it before changing it.
- Error paths and `ExtraAttributesError` quote the data's *keys*, never its values, and a refused
  UUID names the one character the reader stopped at.
- Sets, frozensets and dict keys of `int`, `float`, `Decimal` or `UUID` use CPython's
  non-randomised hashes, so crafted data is quadratic: cap request sizes before decoding.
- Hostile or broken application types — a raising metaclass, a hash that changes, a re-entrant
  `__eq__` — are refused or rebuilt on each use rather than supported. Through `Serializer`, a
  value whose class cannot be hashed raises that class's own error unless `type_` is given.
- Application code is trusted, so its words come through: a validator that calls the standard
  library and lets its error out keeps that error's message, which may quote the input, and the
  same goes for third-party validator packages. A few application messages are replaced by a
  fixed "the input is not valid for its type" — a deprecated v1 `@validator`, a
  `singledispatch`-wrapped validator, `model_post_init` with private attributes, a raising
  `annotated_types.Predicate`, a validator compiled to C. Nothing leaks; the wording is lost.

### Class hierarchies

- Name every class of a hierarchy before a type holding one is used — and before a model holding
  one is defined, as a model builds its schema then. Naming one later raises `MappingError`.
  Hierarchy classes live for the whole process.
- Reading a nested hierarchy value costs depth × size; the decoder caps nesting at about 198
  levels.

### The bundle

- A class subclassing a normalizer or encoder interface is tagged before its own
  `@autoconfigure_tag(...)` is read, so those attributes are dropped and it joins the default
  serializer at its definition's priority. Tag it where you register it, or use
  `@as_tagged_item(priority=...)`.
- Configure serializers through `SerializerConfig` and the tags. Registering `Serializer`
  yourself, or overriding a built-in, drops the bundle's tag attributes.
- A decorator wraps the default serializer's instance only; each named serializer holds its own
  undecorated copy, keyed `serializer.<name>[.<qualifier>]`.
- Strings in a configured default context go through `%parameter%` resolution twice, so a
  literal `%` is written `%%%%`, and `'%%kernel.environment%%'` arrives as `'dev'`. A string
  such as `'10%%-20%%'` fails the boot with `ParameterNotFoundError` for the parameter `-20`.
  Every serializer is built at boot, so an `env()` variable that is not set fails the boot.

### debug:serializer

- It takes a class. A parametrized generic alias of a dataclass (`Box[int]`, `list[int]`) and a
  TypeVar are refused; pydantic generic models (`Page[int]`) work. Running it on a class of a
  hierarchy locks that hierarchy for the process, so naming a subclass afterwards raises
  `MappingError`.
- Its tables are pydantic's JSON schema, with that schema's blind spots: an `AliasPath` shows as
  the field name and `AliasChoices` as its first choice, `SkipJsonSchema` fields are hidden,
  `bytes` show as `string (binary)` though they are written base64url, and a serialization field
  with a default says "Required: no" though it is always written. A field with no JSON schema
  shows as `any`, which means "no JSON schema", not "accepts anything".
- The tables assume the default options, aliases on; a serializer's configured default context is
  not reflected in them.
- An application JSON-schema hook raising `TypeError` or `ValueError` makes the command refuse
  the class in one line; any other exception is printed in that hook's words, and an integer
  default over 4300 digits stops it with Python's own error.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-serializer`; run the commands below from there. The `python-xtr-serializer`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

The exactness promise is tested by a seeded property test that generates nested dataclass and
model types, polymorphic fields among them, and checks every generated value back.

## License

MIT — see [LICENSE](LICENSE).
