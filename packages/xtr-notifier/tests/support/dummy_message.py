"""A message of no particular channel, for tests that only route or record one."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_notifier.message import MessageOptions

__all__ = ["DummyMessage"]


@dataclass(frozen=True)
class DummyMessage:
    """A message every field of which a test can set."""

    subject: str = "subject"
    recipient_id: str | None = "recipient_id"
    options: MessageOptions | None = None
    transport: str | None = None
