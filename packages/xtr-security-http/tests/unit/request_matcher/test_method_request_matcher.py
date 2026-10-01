"""The method matcher claims a request by its HTTP method, case-insensitively."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.requests import make_request
from xtr_security_http.request_matcher.method_request_matcher import MethodRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _request(method: str) -> Request:
    return make_request(method=method)


def test_it_claims_a_listed_method() -> None:
    matcher = MethodRequestMatcher(["POST", "PUT"])
    assert matcher.matches(_request("POST"))


def test_it_matches_case_insensitively() -> None:
    matcher = MethodRequestMatcher(["post"])
    assert matcher.matches(_request("POST"))


def test_it_declines_an_unlisted_method() -> None:
    matcher = MethodRequestMatcher(["POST"])
    assert not matcher.matches(_request("GET"))
