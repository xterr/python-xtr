from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from xtr_webhook.client import IsJsonRequestMatcher


def _with_content_type(content_type: str) -> ServerRequest:
    return ServerRequest("POST", "/webhook", {"Content-Type": content_type})


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "application/json; charset=utf-8",
        "application/vnd.x+json",
        "application/vnd.x+json; charset=utf-8",
        "Application/JSON",
        "  application/json  ",
    ],
)
def test_it_claims_a_request_carrying_a_json_media_type(content_type: str) -> None:
    assert IsJsonRequestMatcher().matches(_with_content_type(content_type)) is True


@pytest.mark.parametrize(
    "content_type",
    [
        "text/plain",
        "application/jsonish",
        "application/x-www-form-urlencoded",
        "application/json-patch",
    ],
)
def test_it_refuses_a_request_carrying_another_media_type(content_type: str) -> None:
    assert IsJsonRequestMatcher().matches(_with_content_type(content_type)) is False


def test_it_refuses_a_request_carrying_no_content_type() -> None:
    assert IsJsonRequestMatcher().matches(ServerRequest("POST", "/webhook")) is False
