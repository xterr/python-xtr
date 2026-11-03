"""A factory an application tags for the mailer: ``fake://<name>``, keeping what each sends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_mailer.exception import TransportError
from xtr_mailer.transport import AbstractTransport, AbstractTransportFactory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_mailer import SentMessage
    from xtr_mailer.transport import Dsn

__all__ = ["DOWN", "RecordingTransportFactory"]

DOWN: Final = "down"
"""The name of a recording transport that fails every send."""


@final
class _RecordingTransport(AbstractTransport):
    """Keeps each email under its name; the one named :data:`DOWN` fails instead."""

    def __init__(self, name: str, sent: list[tuple[str, SentMessage]]) -> None:
        super().__init__()
        self._name = name
        self._sent = sent

    @override
    async def _do_send(self, message: SentMessage) -> None:
        if self._name == DOWN:
            raise TransportError("The fake server is down.")
        self._sent.append((self._name, message))

    @override
    def __str__(self) -> str:
        return f"fake://{self._name}"


@final
class RecordingTransportFactory(AbstractTransportFactory):
    """Serves ``fake://<name>``; every transport it builds keeps what it sends in :attr:`sent`."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[tuple[str, SentMessage]] = []

    @override
    def create(self, dsn: Dsn) -> AbstractTransport:
        return _RecordingTransport(dsn.host, self.sent)

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("fake",)
