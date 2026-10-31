"""The application's own services: a consumer, a parser probe, a parser of event lists."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target, as_service
from xtr_http_foundation import IsJsonRequestMatcher, RequestMatcherInterface
from xtr_remote_event import RemoteEvent
from xtr_remote_event.decorator import as_remote_event_consumer

from xtr_webhook.client import AbstractRequestParser, RequestParserInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

CONSUMED: list[RemoteEvent] = []
"""Every event a webhook was turned into, in arrival order."""

LISTED_TYPE = "listed"


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


@final
class EventListRequestParser(AbstractRequestParser):
    """Reads a JSON object of events by id, each one's payload as given but its ``tags`` a set.

    A set is a value no wire carries exactly: the parser hands on what a bus writing its
    messages refuses, as a parser of a real sender may. It verifies nothing.
    """

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        """Claim any request whose body reads as JSON."""
        return IsJsonRequestMatcher()

    @override
    async def do_parse(self, request: ServerRequestInterface, secret: str) -> list[RemoteEvent]:
        """Turn each ``id: payload`` entry into an event, in the order they arrived."""
        del secret
        events: list[RemoteEvent] = []
        for event_id, value in (await self.read_json(request)).items():
            # A fixture's own requests: each value is the object a test posted.
            payload = dict(cast("dict[str, object]", value))
            if isinstance(tags := payload.get("tags"), list):
                payload["tags"] = set(cast("list[str]", tags))
            events.append(RemoteEvent(LISTED_TYPE, event_id, payload))
        return events
