from __future__ import annotations

from xtr_notifier.recipient import (
    EmailRecipientInterface,
    NoRecipient,
    RecipientInterface,
    SmsRecipientInterface,
)


def test_it_is_a_recipient_with_neither_an_email_nor_a_phone() -> None:
    recipient = NoRecipient()

    assert isinstance(recipient, RecipientInterface)
    assert not isinstance(recipient, EmailRecipientInterface)
    assert not isinstance(recipient, SmsRecipientInterface)
