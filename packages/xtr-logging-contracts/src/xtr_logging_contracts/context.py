"""The structured data a caller attaches to what it logs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, TypeAlias

__all__ = ["EXCEPTION_KEY", "Context"]

Context: TypeAlias = Mapping[str, object]
"""Structured data attached to what is logged.

Values are ``object`` because a caller may log anything; an implementation
normalises what it cannot serialise rather than refusing it.
"""

EXCEPTION_KEY: Final = "exception"
"""The context key reserved for an exception to report.

Part of the contract rather than of any implementation: a library puts the
exception it is reporting here, and whatever writes the record knows to look
for it.
"""
