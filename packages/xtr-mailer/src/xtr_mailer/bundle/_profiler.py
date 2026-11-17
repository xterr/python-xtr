"""The profiler panel's collector, registered when the http kernel profiles requests.

Imported only then, so xtr-http-kernel — and the event dispatcher it brings along — is
installed whenever this module is.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, bundle_active
from xtr_event_dispatcher.bundle import LISTENER_TAG
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_mailer.data_collector import MailerDataCollector
from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent

__all__ = ["register_profiler"]

_NAME: Final = "mailer"
_TEMPLATE: Final = "@xtr_mailer/collector/mailer.html.j2"
_PRIORITY: Final = 230


def register_profiler(services: ServiceConfigurator, builder: ContainerBuilder) -> None:
    """Register the collector, listening to every email event, when the dispatcher is active.

    The collector learns of an email only from the events a transport and the mailer
    dispatch; without the event dispatcher bundle there is nothing to hear, so no panel is
    registered.
    """
    if not bundle_active(builder, "event_dispatcher"):
        return
    _ = (
        services.set(MailerDataCollector)
        .add_tag(DATA_COLLECTOR_TAG, name=_NAME, template=_TEMPLATE, priority=_PRIORITY)
        .add_tag(
            LISTENER_TAG,
            event=MessageEvent,
            method="on_message",
            priority=MailerDataCollector.PRIORITY,
        )
        .add_tag(LISTENER_TAG, event=SentMessageEvent, method="on_sent")
        .add_tag(LISTENER_TAG, event=FailedMessageEvent, method="on_failed")
    )
