"""The application's own services: a consumer, a parser probe."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_dependency_injection import Target, as_service
from xtr_remote_event.decorator import as_remote_event_consumer

from xtr_webhook.client import (
    RequestParserInterface,  # noqa: TC001 -- the container reads the probe's annotation at runtime
)

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

CONSUMED: list[RemoteEvent] = []
"""Every event a webhook was turned into, in arrival order."""


@as_remote_event_consumer("plain")
@as_remote_event_consumer("test")
class RecordingConsumer:
    """Keeps every event it was handed, in a module list a served test can reach."""

    async def consume(self, event: RemoteEvent) -> None:
        """Keep ``event``, so a test can say what the webhook became."""
        CONSUMED.append(event)


@as_service
class ParserProbe:
    """Asks for the parser the bundle qualifies ``webhook``, to prove the alias resolves."""

    def __init__(self, parser: Annotated[RequestParserInterface, Target("webhook")]) -> None:
        """Keep the parser the container handed over."""
        self.parser: RequestParserInterface = parser
