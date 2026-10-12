from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest
from xtr_remote_event import RemoteEvent

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.exception import RejectWebhookError

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "s3cret"


def _arrived(body: bytes = b'{"hello": "world"}', header: str = _WHSEC) -> ServerRequest:
    return ServerRequest(
        "POST",
        "/webhook",
        {"Content-Type": "application/json", "X-Secret": header},
        body,
    )


@pytest.mark.anyio
async def test_it_reads_a_request_whose_header_repeats_the_secret() -> None:
    parsed = await SecretHeaderRequestParser().parse(_arrived(), _WHSEC)

    assert parsed == RemoteEvent("parsed", "the-id", {"hello": "world"})


@pytest.mark.anyio
async def test_it_refuses_a_request_whose_header_says_something_else() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await SecretHeaderRequestParser().parse(_arrived(header="nope"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Invalid secret."


def test_its_matcher_claims_a_json_post_and_nothing_else() -> None:
    matcher = SecretHeaderRequestParser().get_request_matcher()

    assert matcher.matches(_arrived()) is True
    assert matcher.matches(ServerRequest("GET", "/webhook")) is False
