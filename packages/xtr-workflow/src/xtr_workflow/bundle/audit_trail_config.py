"""Configuration of the audit trail of a configured workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["AuditTrailConfig"]


@final
@dataclass(frozen=True, slots=True)
class AuditTrailConfig:
    """Whether every move of a workflow's subjects is logged.

    Attributes:
        enabled: Log, on the ``workflow`` channel, each place a subject leaves
            and enters and each transition it takes; off unless enabled.
    """

    enabled: bool = False
