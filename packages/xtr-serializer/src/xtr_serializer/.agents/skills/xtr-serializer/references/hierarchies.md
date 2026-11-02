# Class hierarchies

A field typed with a base class holds a value of any subclass. Declare the hierarchy once on the
base, and name each class that is a value of its own.

```python
from dataclasses import dataclass, field

from xtr_serializer import (
    JsonEncoder,
    NotNormalizableValueError,
    PydanticNormalizer,
    Serializer,
    discriminator_map,
    discriminator_name,
)

serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])


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

A forged, unknown or missing tag is refused:

```python
try:
    serializer.deserialize('{"latest": {"$type": "nowhere", "name": "sent"}}', Mailbox, "json")
except NotNormalizableValueError as refusal:
    print(refusal)
    # at 'latest': the data must be an object whose '$type' names a class the declared type
    # takes (got 'dict')
```

- The wire key is `"$type"` by default — no name a field can have. `@discriminator_map("kind")`
  picks another, which must be no field's name or alias.
- A name is the data's word for the class: choose one that stays when the class moves or is
  renamed. Only a named class is written; a value of an unnamed subclass is refused rather than
  written as its base, so name even a subclass that adds no field.
- A tag is resolved among the registered subclasses **of the declared type only**, so data cannot
  name a class of another hierarchy or one the field does not take.
- Dataclasses, pydantic dataclasses and models all work, as do intermediate bases: a field typed
  with one takes the named classes under it. A generic class cannot be in a hierarchy.
- Apply `@discriminator_map` after `@dataclass`, and before `@discriminator_name` when the base
  has a name of its own.
- Name every class of a hierarchy before a type holding one is used — and before a model holding
  one is defined, as a model builds its schema then. Naming one later raises `MappingError`, and
  hierarchy classes live for the whole process. A model holding its own hierarchy needs
  `model_config = ConfigDict(defer_build=True)`.
- Reading a nested hierarchy value costs depth × size; the decoder caps nesting at about 198
  levels.
