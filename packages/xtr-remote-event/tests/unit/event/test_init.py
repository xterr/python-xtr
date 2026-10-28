from __future__ import annotations

from xtr_remote_event import event

_EXPORTED = ["AbstractMailerEvent", "MailerDeliveryEvent", "MailerEngagementEvent"]


def test_every_exported_name_resolves() -> None:
    assert [name for name in event.__all__ if not hasattr(event, name)] == []


def test_it_exports_the_mailer_events() -> None:
    assert sorted(event.__all__) == _EXPORTED
