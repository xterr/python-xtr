from __future__ import annotations

from xtr_webhook import messenger

_EXPORTED = ["SendWebhookHandler", "SendWebhookMessage"]


def test_every_exported_name_resolves() -> None:
    assert [name for name in messenger.__all__ if not hasattr(messenger, name)] == []


def test_it_exports_the_send_message_and_what_handles_it() -> None:
    assert sorted(messenger.__all__) == _EXPORTED
