# Dates that keep their zone

```python
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer, ZonedDateTime

serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])


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

One string, the form RFC 9557 gives: the ISO datetime with its offset, then the zone's name.

- The same value in a plain `datetime` field is refused when it is written, naming the field: in
  the hour the clocks repeat the offset alone cannot tell the two 03:30s apart.
- `ZonedDateTime` refuses a naive datetime, a fixed offset and a zone with no name; reading
  refuses text not in that form, an unknown zone, and an offset the zone does not have at that
  time. Each unknown zone name is looked up on disk.
- A plain aware `datetime` reads back with pydantic's own `TzInfo`: equal, not the same tzinfo
  object or class.
- `date`, `time`, `timedelta`, `Decimal`, `UUID`, `bytes` (base64url), `Path`, enums, tuples,
  frozensets and sets all round-trip by their declared type, with no annotation.
- More than six fractional-second digits in a datetime are truncated.
- With pydantic before 2.14, a `NamedTuple`'s items are written by their runtime type, so a
  `ZonedDateTime` inside one is refused.
