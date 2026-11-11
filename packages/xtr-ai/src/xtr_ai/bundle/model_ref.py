"""A model on a named platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["ModelRef"]


@final
@dataclass(frozen=True, slots=True)
class ModelRef:
    """The model ``model`` of the platform ``platform``: ``<platform>:<model>``."""

    platform: str
    model: str

    @property
    def model_id(self) -> str:
        """The id runs name the model by."""
        return f"{self.platform}:{self.model}"
