"""What ``ping.txt`` must be read as, for a sender whose captures are not named ``.json``."""

from __future__ import annotations

from xtr_remote_event import RemoteEvent

EXPECTED = RemoteEvent("ping", "p_1", {"type": "ping", "id": "p_1"})
