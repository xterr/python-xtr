"""A transport that records every delivery instead of making one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.server import TransportInterface

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from xtr_webhook.subscriber import Subscriber


@final
class FakeTransport(TransportInterface):
    """Records every ``send`` in ``sends``; ``raises`` makes each one fail.

    The pair is recorded before ``raises`` is thrown, so a test can tell a
    delivery that was never attempted from one that was attempted and
    refused — the difference between a handler that dropped the message and
    one the bus will retry.

    The subscriber and the event are kept as they arrived rather than copied,
    so a test can prove which objects a handler handed over.
    """

    def __init__(self, raises: Exception | None = None) -> None:
        self.sends: list[tuple[Subscriber, RemoteEvent]] = []
        self.raises = raises

    @override
    async def send(self, subscriber: Subscriber, event: RemoteEvent) -> None:
        self.sends.append((subscriber, event))

        if self.raises is not None:
            raise self.raises
