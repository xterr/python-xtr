# Normalizers and encoders of your own

A normalizer handles the types it reports and leaves the rest; the serializer gives each value to
the first one that handles it, in the order the list has them. Put yours before the pydantic
normalizer, which handles nearly anything.

```python
from dataclasses import dataclass

from xtr_serializer import (
    JsonEncoder,
    NotNormalizableValueError,
    PydanticNormalizer,
    Serializer,
)


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
assert serializer.serialize(Point(3, 4), "json") == "[3,4]"
assert serializer.deserialize("[3,4]", Point, "json") == Point(3, 4)
```

- Implement `NormalizerInterface`, `DenormalizerInterface` or both; an encoder implements
  `EncoderInterface`, `DecoderInterface` or both, as `encode`, `supports_encoding`, `decode`,
  `supports_decoding` and a format string of its own. They are `Protocol`s — subclassing is
  optional in code, the methods are what counts, and `normalize` / `supports_normalization` must
  accept the keyword-only `type_`.
- `get_supported_types(format)` is how a serializer skips you without asking: a key is a class
  (standing for its subclasses), `"object"` (every class) or `"*"` (anything at all, type
  expressions such as `int | None` included). Its value is `True` when the answer rests on the
  type and the format alone — asked once per type and remembered — `False` when it rests on the
  value or the context too, and `None` for a type you do not handle.
- A key naming the type itself counts first, so `None` there settles it; failing that, the first
  class key covering the type, in the order reported, counts — so list narrower keys first. A
  class key never covers `list[Point]` or `Point | None`; only `"*"` does.
- **Priority is list order**, both in code and, through the bundle, by the tag's `priority`
  attribute, highest first.
- Take `SerializerAwareInterface`, `NormalizerAwareInterface` or `DenormalizerAwareInterface` and
  the serializer hands itself over, for values nested inside yours.
- `Serializer` does not look inside a bare list or dict: it goes to a normalizer whole, so a
  normalizer of your own is never handed a container's items.
- In a container, a class **subclassing** one of the interfaces is tagged without being told; a
  class that only has their methods is not, and joins nothing until a tag puts it there — see
  [application.md](application.md).
