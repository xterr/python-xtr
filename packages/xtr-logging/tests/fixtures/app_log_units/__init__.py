"""A scoped resource logging from its teardown, for units the logging bundle opens a log unit in.

Logging goes through :data:`HANDLER`, a fingers-crossed buffer per log unit
in front of :data:`SPY`: what reaches the spy is what a unit's error flushed.
"""

from __future__ import annotations

from collections.abc import (
    AsyncIterator,
)
from typing import final

from xtr_dependency_injection import as_service
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import TestHandler
from xtr_logging.handler.fingers_crossed_handler import FingersCrossedHandler

__all__ = ["HANDLER", "SPY", "Resource", "resource"]

SPY = TestHandler()
"""Every record a unit's error let through."""

HANDLER = FingersCrossedHandler(SPY, activation_strategy=Level.ERROR)
"""Buffers each unit's records until one of them is an error."""


@final
class Resource:
    """A scoped resource, named after the unit it was built for."""

    def __init__(self) -> None:
        self.name = ""


@as_service(lifetime="scoped")
async def resource() -> AsyncIterator[Resource]:
    """Hand out one per unit, logging from its teardown."""
    built = Resource()
    yield built
    _ = HANDLER.handle(make_record(Level.DEBUG, f"{built.name} teardown"))
