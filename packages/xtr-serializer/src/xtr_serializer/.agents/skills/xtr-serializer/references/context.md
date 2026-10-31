# Options: the context

Every call takes a context — a plain mapping each step reads its own keys from. A builder per
step sets them with typed methods, and each leaves the other steps' keys alone, so they chain by
handing one's `to_dict()` to the next.

```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from xtr_serializer import (
    JsonEncoder,
    JsonEncoderContextBuilder,
    PydanticNormalizer,
    PydanticNormalizerContextBuilder,
    Serializer,
)


@dataclass(frozen=True)
class Order:
    reference: str
    total: Decimal
    placed_at: datetime


serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
order = Order("A-17", Decimal("19.99"), datetime(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("UTC")))

context = (
    PydanticNormalizerContextBuilder(JsonEncoderContextBuilder().with_indent(2).to_dict())
    .with_ignored_attributes({"total"})
    .to_dict()
)
# {'json_indent': 2, 'ignored_attributes': frozenset({'total'})}

serializer.serialize(order, "json", context)
# '{\n  "reference": "A-17",\n  "placed_at": "2026-03-01T09:30:00Z"\n}'
```

| Builder | Sets |
|---|---|
| `SerializerContextBuilder` | `with_collect_denormalization_errors` |
| `PydanticNormalizerContextBuilder` | `with_attributes`, `with_ignored_attributes`, `with_skip_null_values`, `with_skip_unset_values`, `with_skip_default_values`, `with_by_alias`, `with_strict`, `with_allow_extra_attributes`, `with_from_attributes`, `with_populate_by_name` |
| `JsonEncoderContextBuilder` | `with_indent` |

- Builders are immutable: each `with_*` returns a new one, so a builder holding an application's
  defaults can be extended for a single call.
- Each key is a public constant with the same name in upper case — `STRICT`, `BY_ALIAS`,
  `JSON_INDENT`, `COLLECT_DENORMALIZATION_ERRORS` — for a context written by hand.
- A serializer built with `default_context=` starts every call from those options, and a call's
  context wins over them key by key. With no call context, every call is handed the serializer's
  own mapping: copy it before changing it.
- The whole context also reaches pydantic as `info.context`, so an application's validators read
  it.
- Leaving fields out (`with_attributes`, `with_ignored_attributes`, the `skip_*` options) is a
  partial write: it is checked, but not read back, so the exactness promise does not apply to it.
