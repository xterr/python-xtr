# The bundle in an application

With xtr-dependency-injection installed beside the package, list the bundle:

```python
# app/config/bundles.py
from xtr_serializer.bundle import SerializerBundle

BUNDLES = {SerializerBundle: {"all": True}}
```

Every serializer is registered under `SerializerInterface`, `NormalizerInterface`,
`DenormalizerInterface`, `EncoderInterface` and `DecoderInterface` — the default one with no
qualifier, a named one under its name.

## Configure

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

## Tags

A service joins a serializer by `NORMALIZER_TAG` (`"serializer.normalizer"`) or `ENCODER_TAG`
(`"serializer.encoder"`), with three optional attributes:

| Attribute | Means |
|---|---|
| `priority` | An `int`, higher tried first; without it, the definition's own priority, or 0 |
| `serializer` | The name it joins, or a sequence of names: `"default"` (the default when absent), a configured name, or `"*"` for every serializer |
| `built_in` | `True` for one a named serializer can leave out |

```python
from xtr_serializer.bundle import NORMALIZER_TAG


def load_extension(self, config, services, builder) -> None:
    _ = services.set(MoneyNormalizer).add_tag(NORMALIZER_TAG, priority=10, serializer="*")
```

- A class **subclassing** one of the interfaces carries the tag without being told, with no
  attribute — which puts it in the default serializer at its definition's own priority. A class
  that only has a normalizer's or an encoder's methods carries nothing: tag it where you register
  it. A serializer holds exactly what is tagged for it.
- Such a class is tagged before its own `@autoconfigure_tag(...)` is read, so those attributes are
  dropped. Tag it where you register it, or use `@as_tagged_item(priority=...)`.
- **Checked at build**: a tag that cannot be read, one naming a serializer that does not exist,
  and a serializer left without a normalizer or an encoder all fail the build. Booting then builds
  every serializer, so a service tagged as what it is not fails there rather than on the first
  call.
- **Named copies**: each named serializer gets its own instance of every service it shares with
  another, under the key `serializer.<name>[.<qualifier>]` — a service is handed the serializer
  holding it, and one instance can only be handed one. A decorator wraps the default serializer's
  instance only.
- Strings in a configured default context go through `%parameter%` resolution twice, so a literal
  `%` is written `%%%%`, and `'%%kernel.environment%%'` arrives as `'dev'`. A string such as
  `'10%%-20%%'` fails the boot with `ParameterNotFoundError` for the parameter `-20`.
- **Zero config**: one serializer writing JSON. Nothing is converted until something asks for one.

## debug:serializer

In debug mode, with a console bundle active, `debug:serializer <module:Class>` shows the fields of
a class as it is read (`validation`) and as it is written (`serialization`), and the classes of its
hierarchy. It takes a class: a parametrized generic alias (`Box[int]`, `list[int]`) and a TypeVar
are refused, while pydantic generic models (`Page[int]`) work. Running it on a class of a hierarchy
locks that hierarchy for the process. Its tables are pydantic's JSON schema, with that schema's
blind spots, and assume the default options rather than a configured default context.
