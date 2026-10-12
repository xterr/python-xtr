"""A configurator that records every call and applies a scripted write."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.server import RequestConfiguratorInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_remote_event import RemoteEvent

    from xtr_webhook.server import OutgoingRequest


@final
class FakeRequestConfigurator(RequestConfiguratorInterface):
    """Records what it was handed; ``write`` scripts what it does to the request.

    The calls keep the request object itself rather than a copy, so a test can
    see that a chain hands every step the same request — and, through ``write``,
    script one step's contribution and read it back from a later one.
    """

    def __init__(self, write: Callable[[OutgoingRequest], None] | None = None) -> None:
        self.write = write
        self.calls: list[tuple[RemoteEvent, str, OutgoingRequest]] = []

    @override
    def configure(self, event: RemoteEvent, secret: str, request: OutgoingRequest) -> None:
        self.calls.append((event, secret, request))

        if self.write is not None:
            self.write(request)
