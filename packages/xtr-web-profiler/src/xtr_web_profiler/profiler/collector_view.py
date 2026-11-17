"""One collector's data, as a panel template reads it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["CollectorView"]


@dataclass(frozen=True, slots=True)
class CollectorView:
    """What a panel template knows as ``collector``.

    Attributes:
        name: The collector's name.
        data: What it kept of the request, as the profile stored it —
            ``collector.data.method``, ``collector.data["status_code"]``.
    """

    name: str
    data: Mapping[str, object]
