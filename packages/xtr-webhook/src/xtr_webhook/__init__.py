"""Webhooks received as events, and sent signed.

An incoming request is checked against the secret of the subscriber it claims to come from,
bounded to a window so a captured one cannot be replayed, and turned into an event. An
outgoing one is signed the same way and sent through a message bus, so a refusal is retried.
"""

from __future__ import annotations

__all__: list[str] = []
