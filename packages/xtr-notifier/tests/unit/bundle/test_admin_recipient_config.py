from __future__ import annotations

import pytest

from xtr_notifier.bundle import AdminRecipientConfig
from xtr_notifier.exception import InvalidArgumentError


def test_it_needs_an_email_and_defaults_to_no_phone() -> None:
    admin = AdminRecipientConfig("admin@example.test")

    assert admin.email == "admin@example.test"
    assert admin.phone == ""


def test_it_refuses_an_empty_email() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = AdminRecipientConfig("")

    assert str(caught.value) == "An admin recipient needs an email."
