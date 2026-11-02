"""The envelope serializer every test encodes with, as the messenger bundle builds it."""

from __future__ import annotations

from typing import Final

from xtr_messenger import JsonSerializer
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

SERIALIZER: Final = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
