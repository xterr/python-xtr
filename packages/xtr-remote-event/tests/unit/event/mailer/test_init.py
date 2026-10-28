from __future__ import annotations

from xtr_remote_event.event import mailer

_EXPORTED = ["AbstractMailerEvent", "MailerDeliveryEvent", "MailerEngagementEvent"]


def test_every_exported_name_resolves() -> None:
    assert [name for name in mailer.__all__ if not hasattr(mailer, name)] == []


def test_it_exports_the_mailer_events() -> None:
    assert sorted(mailer.__all__) == _EXPORTED
