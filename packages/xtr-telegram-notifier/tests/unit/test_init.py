from __future__ import annotations

import xtr_telegram_notifier
from xtr_telegram_notifier import TelegramOptions, TelegramTransport, TelegramTransportFactory


def test_it_exports_the_transport_its_factory_and_its_options() -> None:
    assert xtr_telegram_notifier.__all__ == [
        "TelegramOptions",
        "TelegramTransport",
        "TelegramTransportFactory",
    ]
    assert xtr_telegram_notifier.TelegramOptions is TelegramOptions
    assert xtr_telegram_notifier.TelegramTransport is TelegramTransport
    assert xtr_telegram_notifier.TelegramTransportFactory is TelegramTransportFactory
