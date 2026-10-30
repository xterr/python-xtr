"""The check data passes to be written as JSON: JSON's own types only, every number finite."""

from __future__ import annotations

from typing import Final

from pydantic import ConfigDict, TypeAdapter

from xtr_serializer.normalized_value import NormalizedValue

__all__ = ["PLAIN_DATA"]

# Strict: only JSON's own types pass, not a tuple or a set. Finite: NaN and infinity are refused.
# An error's ``loc`` alternates each JSON value's union tag with the key or index under it.
PLAIN_DATA: Final[TypeAdapter[NormalizedValue]] = TypeAdapter(
    NormalizedValue, config=ConfigDict(strict=True, allow_inf_nan=False)
)
