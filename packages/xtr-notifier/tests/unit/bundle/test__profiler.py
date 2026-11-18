from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast, final

from xtr_event_dispatcher.bundle import LISTENER_TAG
from xtr_http_kernel.data_collector import DATA_COLLECTOR_TAG

from xtr_notifier.bundle._profiler import notifier_data_collector, register_profiler
from xtr_notifier.data_collector import NotifierDataCollector
from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator


@final
class _Services:
    """Notes what is registered, and the tags it is given."""

    def __init__(self) -> None:
        self.registered: list[object] = []
        self.tags: list[tuple[str, dict[str, object]]] = []

    def set(self, target: object) -> Self:
        self.registered.append(target)
        return self

    def add_tag(self, tag: str, /, **attributes: object) -> Self:
        self.tags.append((tag, attributes))
        return self


def test_the_collector_is_registered_as_the_notifier_panel_and_a_message_listener() -> None:
    services = _Services()

    register_profiler(cast("ServiceConfigurator", cast("object", services)))

    assert services.registered == [notifier_data_collector]
    assert services.tags == [
        (
            DATA_COLLECTOR_TAG,
            {
                "name": "notifier",
                "template": "@xtr_notifier/collector/notifier.html.j2",
                "priority": 225,
            },
        ),
        (LISTENER_TAG, {"event": MessageEvent, "method": "on_message"}),
        (LISTENER_TAG, {"event": SentMessageEvent, "method": "on_sent_message"}),
        (LISTENER_TAG, {"event": FailedMessageEvent, "method": "on_failed_message"}),
    ]


def test_the_factory_builds_a_collector() -> None:
    assert isinstance(notifier_data_collector(), NotifierDataCollector)
