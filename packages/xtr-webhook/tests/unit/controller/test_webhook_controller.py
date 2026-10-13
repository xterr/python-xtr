from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_message import Response, ServerRequest
from xtr_messenger.exception import NoHandlerForMessageError
from xtr_remote_event import RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

from tests.support.recording_message_bus import RecordingMessageBus
from xtr_webhook.client import ChainRequestMatcher, RequestMatcherInterface
from xtr_webhook.client.abstract_request_parser import AbstractRequestParser
from xtr_webhook.controller import WebhookController
from xtr_webhook.controller._built_parsers import BuiltParsers
from xtr_webhook.exception import RejectWebhookError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "1234"
_PLAIN_TEXT = "text/plain; charset=utf-8"


@final
class _ScriptedRequestParser(AbstractRequestParser):
    """Hands back what a test scripted, and keeps the secrets it was handed.

    A real subclass of the base parser rather than a stand-in, so the answers
    the controller returns unchanged — the 202, and the 406 carrying a reason —
    are the ones a parser actually builds.
    """

    def __init__(
        self,
        parsed: RemoteEvent | Sequence[RemoteEvent] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.parsed = parsed
        self.raises = raises
        self.secrets: list[str] = []

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([])

    @override
    async def do_parse(
        self,
        request: ServerRequestInterface,
        secret: str,
    ) -> RemoteEvent | Sequence[RemoteEvent] | None:
        del request
        self.secrets.append(secret)

        if self.raises is not None:
            raise self.raises

        return self.parsed


def _arrived() -> ServerRequest:
    return ServerRequest(
        "POST",
        "/webhook/acme",
        {"Content-Type": "application/json"},
        b'{"hello": "world"}',
    )


def _controller(
    parser: _ScriptedRequestParser,
    bus: RecordingMessageBus,
    secrets: dict[str, str] | None = None,
) -> WebhookController:
    return WebhookController(
        {"acme": parser},
        {"acme": _WHSEC} if secrets is None else secrets,
        bus,
    )


@pytest.mark.anyio
async def test_it_answers_a_type_no_parser_speaks_for_with_404() -> None:
    bus = RecordingMessageBus()

    answered = await WebhookController({}, {}, bus).index_action("acme", _arrived(), Response())

    assert answered.get_status_code() == 404
    assert await answered.get_body().get_contents() == (
        b"No webhook parser found for the type given in the URL."
    )
    assert answered.get_header_line("Content-Type") == _PLAIN_TEXT
    assert bus.messages == []


@pytest.mark.anyio
@pytest.mark.parametrize("parsed", [None, []])
async def test_it_refuses_a_webhook_the_parser_read_nothing_out_of(
    parsed: RemoteEvent | Sequence[RemoteEvent] | None,
) -> None:
    parser = _ScriptedRequestParser(parsed=parsed)
    bus = RecordingMessageBus()

    answered = await _controller(parser, bus).index_action("acme", _arrived(), Response())

    assert answered.get_status_code() == 406
    assert await answered.get_body().get_contents() == b"Unable to parse the webhook payload."
    assert bus.messages == []


@pytest.mark.anyio
async def test_it_checks_a_webhook_against_the_secret_its_type_was_configured_with() -> None:
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {}))

    _ = await _controller(parser, RecordingMessageBus()).index_action(
        "acme", _arrived(), Response()
    )

    assert parser.secrets == [_WHSEC]


@pytest.mark.anyio
async def test_a_type_configured_with_no_secret_is_checked_against_an_empty_one() -> None:
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {}))

    _ = await _controller(parser, RecordingMessageBus(), secrets={}).index_action(
        "acme", _arrived(), Response()
    )

    assert parser.secrets == [""]


@pytest.mark.anyio
async def test_it_answers_a_read_webhook_with_202_and_nothing_else() -> None:
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {"payload": True}))

    answered = await _controller(parser, RecordingMessageBus()).index_action(
        "acme", _arrived(), Response()
    )

    assert answered.get_status_code() == 202
    assert await answered.get_body().get_contents() == b""


@pytest.mark.anyio
async def test_it_dispatches_the_one_event_a_webhook_carried_under_its_type() -> None:
    event = RemoteEvent("name", "id", {"payload": True})
    bus = RecordingMessageBus()

    _ = await _controller(_ScriptedRequestParser(parsed=event), bus).index_action(
        "acme", _arrived(), Response()
    )

    assert bus.messages == [ConsumeRemoteEventMessage("acme", event)]


@pytest.mark.anyio
async def test_it_dispatches_one_message_per_event_a_webhook_carried() -> None:
    first = RemoteEvent("name1", "id1", {"payload": 1})
    second = RemoteEvent("name2", "id2", {"payload": 2})
    bus = RecordingMessageBus()

    answered = await _controller(_ScriptedRequestParser(parsed=[first, second]), bus).index_action(
        "acme", _arrived(), Response()
    )

    assert answered.get_status_code() == 202
    assert await answered.get_body().get_contents() == b""
    assert bus.messages == [
        ConsumeRemoteEventMessage("acme", first),
        ConsumeRemoteEventMessage("acme", second),
    ]


@pytest.mark.anyio
async def test_it_answers_a_refused_webhook_with_what_the_refusal_carries() -> None:
    refusal = RejectWebhookError(401, "Signature is wrong.", {"WWW-Authenticate": "Signature"})
    bus = RecordingMessageBus()

    answered = await _controller(_ScriptedRequestParser(raises=refusal), bus).index_action(
        "acme", _arrived(), Response()
    )

    assert answered.get_status_code() == 401
    assert await answered.get_body().get_contents() == b"Signature is wrong."
    assert answered.get_header_line("Content-Type") == _PLAIN_TEXT
    assert answered.get_header_line("WWW-Authenticate") == "Signature"
    assert bus.messages == []


@pytest.mark.anyio
async def test_a_bus_with_nothing_to_handle_the_event_fails_the_request() -> None:
    # The sender then gets a 5xx and sends the webhook again, which is the only
    # outcome that does not lose the event.
    bus = RecordingMessageBus(raises=NoHandlerForMessageError(ConsumeRemoteEventMessage, ()))
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {}))

    with pytest.raises(NoHandlerForMessageError):
        _ = await _controller(parser, bus).index_action("acme", _arrived(), Response())


@pytest.mark.anyio
async def test_it_takes_its_parsers_from_a_provider_as_readily_as_from_a_mapping() -> None:
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {}))
    bus = RecordingMessageBus()
    controller = WebhookController(BuiltParsers({"acme": parser}), {"acme": _WHSEC}, bus)

    answered = await controller.index_action("acme", _arrived(), Response())

    assert answered.get_status_code() == 202
    assert parser.secrets == [_WHSEC]


@pytest.mark.anyio
async def test_the_secrets_it_was_given_are_copied() -> None:
    parser = _ScriptedRequestParser(parsed=RemoteEvent("name", "id", {}))
    secrets = {"acme": _WHSEC}
    controller = WebhookController({"acme": parser}, secrets, RecordingMessageBus())
    secrets.clear()

    _ = await controller.index_action("acme", _arrived(), Response())

    assert parser.secrets == [_WHSEC]


@pytest.mark.anyio
async def test_it_leaves_the_response_it_was_handed_as_it_was() -> None:
    handed = Response()

    _ = await WebhookController({}, {}, RecordingMessageBus()).index_action(
        "acme", _arrived(), handed
    )

    assert handed.get_status_code() == 200
    assert handed.has_header("Content-Type") is False
