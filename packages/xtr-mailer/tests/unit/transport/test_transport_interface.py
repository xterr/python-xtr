from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mailer.transport import TransportInterface

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer import Envelope, SentMessage


class _Structural:
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        del message, envelope
        return None


def test_anything_that_sends_is_a_transport() -> None:
    assert isinstance(_Structural(), TransportInterface)


def test_something_that_cannot_send_is_not_a_transport() -> None:
    assert not isinstance(object(), TransportInterface)
