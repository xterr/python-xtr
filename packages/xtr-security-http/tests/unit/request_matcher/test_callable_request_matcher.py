"""The callable matcher defers the claim to the callable it holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.requests import make_request
from xtr_security_http.request_matcher.callable_request_matcher import CallableRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _has_ok_header(request: Request) -> bool:
    return request.headers.get("x-ok") == "1"


def test_it_claims_a_request_the_callable_accepts() -> None:
    matcher = CallableRequestMatcher(_has_ok_header)
    assert matcher.matches(make_request(headers={"x-ok": "1"}))


def test_it_declines_a_request_the_callable_rejects() -> None:
    matcher = CallableRequestMatcher(_has_ok_header)
    assert not matcher.matches(make_request())
