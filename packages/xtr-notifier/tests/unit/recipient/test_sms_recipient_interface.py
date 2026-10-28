from __future__ import annotations

from xtr_notifier.recipient import EmailRecipientInterface, SmsRecipientInterface


class _User:
    @property
    def phone(self) -> str:
        return "+3312345678"


def test_anything_with_a_phone_is_an_sms_recipient() -> None:
    assert isinstance(_User(), SmsRecipientInterface)
    assert not isinstance(_User(), EmailRecipientInterface)
