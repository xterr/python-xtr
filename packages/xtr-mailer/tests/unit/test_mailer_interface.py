"""Anything with the mailer's send method is a mailer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mailer import MailerInterface

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer import Envelope


class _Structural:
    async def send(self, message: RawMessage, envelope: Envelope | None = None) -> None:
        del message, envelope


def test_anything_that_sends_is_a_mailer() -> None:
    assert isinstance(_Structural(), MailerInterface)


def test_something_that_cannot_send_is_not_a_mailer() -> None:
    assert not isinstance(object(), MailerInterface)
