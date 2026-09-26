"""What a listener is."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

__all__ = ["Listener"]

Listener: TypeAlias = Callable[..., object]
"""A callable run when an event it listens to is dispatched.

A dispatcher calls it with the event, the name the event was dispatched
under, and the dispatcher itself — as many of the three, in that order, as it
takes positionally; a listener caring only about the event takes one. What it
returns is ignored, except that an awaitable is awaited before the next
listener runs, so a listener is a plain function or an ``async def`` alike.
"""
