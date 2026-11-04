"""A transport standing for the host its DSN named, never sending anything."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mailer.transport import TransportInterface

if TYPE_CHECKING:
    from xtr_mime import RawMessage

    from xtr_mailer import Envelope, SentMessage

__all__ = ["DummyTransport"]


@final
class DummyTransport(TransportInterface):
    """Keeps the host it was built for; a send is a test mistake."""

    def __init__(self, host: str) -> None:
        self.host = host

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        del message, envelope
        msg = "A dummy transport never sends."
        raise AssertionError(msg)

    @override
    def __str__(self) -> str:
        return f"dummy://{self.host}"
