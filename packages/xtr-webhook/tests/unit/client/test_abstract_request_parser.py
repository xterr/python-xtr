from __future__ import annotations

import io
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_foundation import ChainRequestMatcher, RequestMatcherInterface
from xtr_http_message import Response, ServerRequest
from xtr_remote_event import RemoteEvent

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.client import AbstractRequestParser
from xtr_webhook.exception import RejectWebhookError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "s3cret"


@final
class _TextRequestParser(AbstractRequestParser):
    """Reads the body as text, so the base class can be caught mapping a decode failure."""

    __slots__ = ()

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([])

    @override
    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent | None:
        return RemoteEvent("text", "the-id", {"body": (await self.read_body(request)).decode()})


@final
class _AnyBodyRequestParser(AbstractRequestParser):
    """Reads the body as a JSON object whatever it holds, claiming every request.

    Its matcher constrains nothing, so the body reaches :meth:`read_json` even
    when it is not JSON — which is how the base class can be caught turning a
    decode failure into a refusal rather than into a 500.
    """

    __slots__ = ()

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([])

    @override
    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent | None:
        return RemoteEvent("any", "the-id", await self.read_json(request))


class _Unseekable(io.BytesIO):
    """A body that arrived streaming: readable once, from wherever it now stands."""

    @override
    def seekable(self) -> bool:
        return False


def _arrived(body: bytes = b'{"hello": "world"}') -> ServerRequest:
    return ServerRequest(
        "POST",
        "/webhook",
        {"Content-Type": "application/json", "X-Secret": _WHSEC},
        body,
    )


@pytest.mark.anyio
async def test_it_turns_a_request_it_claims_into_an_event() -> None:
    parsed = await SecretHeaderRequestParser().parse(_arrived(), _WHSEC)

    assert parsed == RemoteEvent("parsed", "the-id", {"hello": "world"})


@pytest.mark.anyio
async def test_it_refuses_a_request_its_matcher_does_not_claim() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await SecretHeaderRequestParser().parse(ServerRequest("GET", "/webhook"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_refuses_a_body_that_is_not_json() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _AnyBodyRequestParser().parse(_arrived(b"{not json"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request body is malformed."


@pytest.mark.anyio
async def test_a_matcher_reading_the_body_turns_a_body_that_is_not_json_away_first() -> None:
    # The media type announced JSON; what arrived was not, so the matcher
    # refuses it before the parser is handed anything to decode.
    with pytest.raises(RejectWebhookError) as refused:
        _ = await SecretHeaderRequestParser().parse(_arrived(b"{not json"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_claims_a_json_body_that_announces_nothing() -> None:
    unannounced = ServerRequest("POST", "/webhook", {"X-Secret": _WHSEC}, b'{"hello": "world"}')

    parsed = await SecretHeaderRequestParser().parse(unannounced, _WHSEC)

    assert parsed == RemoteEvent("parsed", "the-id", {"hello": "world"})


@pytest.mark.anyio
async def test_it_refuses_json_that_is_not_an_object() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await SecretHeaderRequestParser().parse(_arrived(b"[1, 2]"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request body is malformed."


@pytest.mark.anyio
async def test_it_refuses_a_body_that_is_not_text() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _TextRequestParser().parse(_arrived(b"\xff"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request body is malformed."


@pytest.mark.anyio
async def test_the_refusal_keeps_what_gave_it_away_to_itself() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _AnyBodyRequestParser().parse(_arrived(b"{not json"), _WHSEC)

    assert isinstance(refused.value.__cause__, Exception)


@pytest.mark.anyio
async def test_it_reads_a_body_another_reader_already_ran_through() -> None:
    request = _arrived()
    _ = await request.get_body().get_contents()

    assert await SecretHeaderRequestParser().read_body(request) == b'{"hello": "world"}'


@pytest.mark.anyio
async def test_it_reads_a_body_that_cannot_be_rewound_from_where_it_stands() -> None:
    request = ServerRequest(
        "POST", "/webhook", {"Content-Type": "application/json"}, _Unseekable(b'{"hi": 1}')
    )
    _ = await request.get_body().read(1)

    assert await SecretHeaderRequestParser().read_body(request) == b'"hi": 1}'


@pytest.mark.anyio
async def test_it_reads_a_json_object_out_of_the_body() -> None:
    assert await SecretHeaderRequestParser().read_json(_arrived()) == {"hello": "world"}


@pytest.mark.anyio
async def test_it_answers_a_parsed_webhook_with_202() -> None:
    answered = await SecretHeaderRequestParser().create_successful_response(_arrived(), Response())

    assert answered.get_status_code() == 202
    assert await answered.get_body().get_contents() == b""


@pytest.mark.anyio
async def test_it_answers_a_refused_webhook_with_406_and_the_reason() -> None:
    answered = await SecretHeaderRequestParser().create_rejected_response(
        "Request does not match.", _arrived(), Response()
    )

    assert answered.get_status_code() == 406
    assert await answered.get_body().get_contents() == b"Request does not match."
    assert answered.get_header_line("Content-Type") == "text/plain; charset=utf-8"


@pytest.mark.anyio
async def test_it_leaves_the_response_it_was_handed_as_it_was() -> None:
    handed = Response()

    _ = await SecretHeaderRequestParser().create_rejected_response("Nope.", _arrived(), handed)

    assert handed.get_status_code() == 200
    assert handed.has_header("Content-Type") is False
