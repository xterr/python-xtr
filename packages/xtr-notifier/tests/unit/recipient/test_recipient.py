from __future__ import annotations

import pytest

from xtr_notifier.exception import InvalidArgumentError
from xtr_notifier.recipient import (
    EmailRecipientInterface,
    Recipient,
    RecipientInterface,
    SmsRecipientInterface,
)


def test_it_cannot_be_built_without_an_email_and_without_a_phone() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Recipient("", "")

    assert str(caught.value) == '"Recipient" needs an email or a phone but both cannot be empty.'


@pytest.mark.parametrize(
    ("email", "phone"),
    [("test@test.de", "+0815"), ("test@test.de", ""), ("", "+0815")],
)
def test_it_is_built_with_an_email_or_a_phone(email: str, phone: str) -> None:
    recipient = Recipient(email, phone)

    assert recipient.email == email
    assert recipient.phone == phone


def test_its_email_and_phone_can_be_changed() -> None:
    recipient = Recipient("test@test.de", "+0815")

    recipient.email = "test@test.com"
    recipient.phone = "+49815"

    assert recipient.email == "test@test.com"
    assert recipient.phone == "+49815"


def test_it_is_an_email_and_an_sms_recipient() -> None:
    recipient = Recipient(phone="+0815")

    assert isinstance(recipient, RecipientInterface)
    assert isinstance(recipient, EmailRecipientInterface)
    assert isinstance(recipient, SmsRecipientInterface)
