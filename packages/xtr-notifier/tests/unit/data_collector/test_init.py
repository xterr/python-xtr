from __future__ import annotations

from xtr_notifier import data_collector
from xtr_notifier.data_collector.notified_message import NotifiedMessage
from xtr_notifier.data_collector.notifier_data_collector import NotifierDataCollector


def test_the_package_re_exports_its_public_classes() -> None:
    assert data_collector.__all__ == ["NotifiedMessage", "NotifierDataCollector"]
    assert (data_collector.NotifiedMessage, data_collector.NotifierDataCollector) == (
        NotifiedMessage,
        NotifierDataCollector,
    )
