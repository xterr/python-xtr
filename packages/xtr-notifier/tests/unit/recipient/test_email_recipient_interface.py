from __future__ import annotations

from xtr_notifier.recipient import EmailRecipientInterface, SmsRecipientInterface


class _User:
    @property
    def email(self) -> str:
        return "user@example.test"


def test_anything_with_an_email_is_an_email_recipient() -> None:
    assert isinstance(_User(), EmailRecipientInterface)
    assert not isinstance(_User(), SmsRecipientInterface)
