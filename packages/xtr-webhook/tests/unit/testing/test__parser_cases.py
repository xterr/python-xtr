from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_remote_event import RemoteEvent

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.client import (
    AbstractRequestParser,
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    RequestMatcherInterface,
)
from xtr_webhook.exception import InvalidArgumentError, RejectWebhookError
from xtr_webhook.testing import ParserCase, assert_parses, parser_cases

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "parser_cases"
_EVENTS = _FIXTURES / "events"
_TEXT = _FIXTURES / "text"

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "s3cret"


def _event(payload: dict[str, object]) -> RemoteEvent:
    return RemoteEvent(str(payload["type"]), str(payload["id"]), payload)


def _case_id(case: ParserCase) -> str:
    """Name each case in the report by the file it came from."""
    return case.id


@final
class _OrderRequestParser(AbstractRequestParser):
    """Reads one order event, or one per entry when the sender batched several."""

    __slots__ = ()

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    @override
    async def do_parse(
        self,
        request: ServerRequestInterface,
        secret: str,
    ) -> RemoteEvent | list[RemoteEvent]:
        del secret
        payload = self.read_json(request)
        batched = payload.get("events")
        if batched is None:
            return _event(payload)

        return [_event(entry) for entry in cast("list[dict[str, object]]", batched)]


@pytest.mark.anyio
@pytest.mark.parametrize("case", parser_cases(_EVENTS), ids=_case_id)
async def test_it_reads_every_fixture_as_its_expectation_file_says(case: ParserCase) -> None:
    await assert_parses(_OrderRequestParser(), case)


def test_it_walks_the_directory_and_sorts_the_pairs_it_finds() -> None:
    assert [case.id for case in parser_cases(_EVENTS)] == [
        "batch/refunds.json",
        "order_paid.json",
    ]


def test_it_reads_the_payload_exactly_as_it_lies_on_disk() -> None:
    found = {case.id: case.payload for case in parser_cases(_EVENTS)}

    assert found["order_paid.json"] == (_EVENTS / "order_paid.json").read_bytes()


def test_it_reads_a_single_event_out_of_the_expectation_file() -> None:
    found = {case.id: case.expected for case in parser_cases(_EVENTS)}

    assert found["order_paid.json"] == RemoteEvent(
        "order.paid",
        "ord_1",
        {"type": "order.paid", "id": "ord_1", "amount": 1200},
    )


def test_it_reads_every_event_an_expectation_file_lists() -> None:
    found = {case.id: case.expected for case in parser_cases(_EVENTS)}

    assert found["batch/refunds.json"] == [
        RemoteEvent(
            "order.refunded", "ord_2", {"type": "order.refunded", "id": "ord_2", "amount": 1200}
        ),
        RemoteEvent(
            "order.refunded", "ord_3", {"type": "order.refunded", "id": "ord_3", "amount": 450}
        ),
    ]


def test_it_refuses_a_fixture_with_no_expectation_file_beside_it() -> None:
    orphan = _FIXTURES / "orphan" / "alone.json"

    with pytest.raises(InvalidArgumentError) as refused:
        _ = parser_cases(_FIXTURES / "orphan")

    assert str(refused.value) == (
        f'The fixture "{orphan}" has no expectation file "{orphan.with_suffix(".py")}".'
    )


def test_it_refuses_an_expectation_file_that_names_no_expectation() -> None:
    sibling = _FIXTURES / "no_expectation" / "empty.py"

    with pytest.raises(InvalidArgumentError) as refused:
        _ = parser_cases(_FIXTURES / "no_expectation")

    assert str(refused.value) == f'The expectation file "{sibling}" defines no EXPECTED.'


def test_it_takes_the_extension_the_senders_captures_carry() -> None:
    assert [case.id for case in parser_cases(_TEXT, "txt")] == ["ping.txt"]


@pytest.mark.anyio
async def test_it_drives_a_parser_over_a_fixture_named_by_another_extension() -> None:
    for case in parser_cases(_TEXT, "txt"):
        await assert_parses(_OrderRequestParser(), case)


def test_it_finds_nothing_under_an_extension_no_fixture_carries() -> None:
    assert parser_cases(_TEXT) == []


@pytest.mark.anyio
async def test_it_fails_when_the_parser_reads_something_else() -> None:
    case = ParserCase(
        "order_paid.json",
        b'{"type": "order.paid", "id": "ord_1"}',
        RemoteEvent("order.refunded", "ord_9", {}),
    )

    with pytest.raises(AssertionError):
        await assert_parses(_OrderRequestParser(), case)


@pytest.mark.anyio
async def test_it_hands_the_parser_the_secret_and_the_headers_it_was_given() -> None:
    case = ParserCase(
        "greeting.json",
        b'{"hello": "world"}',
        RemoteEvent("parsed", "the-id", {"hello": "world"}),
    )

    await assert_parses(
        SecretHeaderRequestParser(),
        case,
        secret=_WHSEC,
        headers={"X-Secret": _WHSEC},
    )


@pytest.mark.anyio
async def test_it_sends_no_header_of_its_own_beyond_the_content_type() -> None:
    case = ParserCase("greeting.json", b'{"hello": "world"}', RemoteEvent("parsed", "the-id", {}))

    with pytest.raises(RejectWebhookError) as refused:
        await assert_parses(SecretHeaderRequestParser(), case, secret=_WHSEC)

    assert str(refused.value) == "Invalid secret."


@pytest.mark.anyio
async def test_it_sends_the_method_the_sender_uses() -> None:
    case = ParserCase("greeting.json", b'{"hello": "world"}', RemoteEvent("parsed", "the-id", {}))

    with pytest.raises(RejectWebhookError) as refused:
        await assert_parses(SecretHeaderRequestParser(), case, method="GET")

    assert str(refused.value) == "Request does not match."
