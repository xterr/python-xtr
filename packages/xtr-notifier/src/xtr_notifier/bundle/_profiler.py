"""The notifier's profiler panel, registered while the http kernel profiles requests.

Imported only once the http kernel's bundle is active with its profiler on,
which proves xtr-http-kernel installed, and only with the event dispatcher
bundle active, since the collector records from the message events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_event_dispatcher.bundle import LISTENER_TAG
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_notifier.data_collector import NotifierDataCollector
from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

__all__ = ["notifier_data_collector", "register_profiler"]

_NAME: Final = "notifier"
_TEMPLATE: Final = "@xtr_notifier/collector/notifier.html.j2"
_PRIORITY: Final = 225


def register_profiler(services: ServiceConfigurator) -> None:
    """Register the collector, listening to every message event it records from."""
    _ = (
        services.set(notifier_data_collector)
        .add_tag(DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY)
        .add_tag(LISTENER_TAG, event=MessageEvent, method="on_message")
        .add_tag(LISTENER_TAG, event=SentMessageEvent, method="on_sent_message")
        .add_tag(LISTENER_TAG, event=FailedMessageEvent, method="on_failed_message")
    )


def notifier_data_collector() -> NotifierDataCollector:
    """Build the collector on its own monotonic clock, never the application's."""
    return NotifierDataCollector()
