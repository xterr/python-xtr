"""The message the mailer queues an email on the bus with."""

from __future__ import annotations

import dataclasses

import pytest
from xtr_mime import Address, RawMessage

from xtr_mailer import Envelope
from xtr_mailer.messenger import SendEmailMessage


def test_it_carries_the_email_and_its_envelope() -> None:
    raw = RawMessage("raw")
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])

    message = SendEmailMessage(raw, envelope)

    assert message.message is raw
    assert message.envelope is envelope


def test_without_an_envelope_the_one_the_headers_give_is_used_later() -> None:
    assert SendEmailMessage(RawMessage("raw")).envelope is None


def test_it_cannot_be_changed() -> None:
    message = SendEmailMessage(RawMessage("raw"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning to a frozen field is the point.
        message.envelope = None  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
