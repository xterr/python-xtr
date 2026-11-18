"""The notifier's profiler panel: every message a profiled request sent or queued.

Needs xtr-http-kernel, so it is imported only when its profiler is on: the
bundle then registers :class:`NotifierDataCollector` as a data collector and
as a listener of the message events, which is what it records from.
"""

from __future__ import annotations

from .notified_message import NotifiedMessage
from .notifier_data_collector import NotifierDataCollector

__all__ = ["NotifiedMessage", "NotifierDataCollector"]
