"""The chain matcher claims a request only when every part does."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.requests import make_request
from xtr_security_http.request_matcher.chain_request_matcher import ChainRequestMatcher
from xtr_security_http.request_matcher.method_request_matcher import MethodRequestMatcher
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _request(path: str, method: str) -> Request:
    request = make_request(method=method)
    request.scope["path"] = path
    return request


def test_it_claims_a_request_every_part_claims() -> None:
    matcher = ChainRequestMatcher([PathRequestMatcher(r"^/api"), MethodRequestMatcher(["POST"])])
    assert matcher.matches(_request("/api/books", "POST"))


def test_it_declines_when_one_part_declines() -> None:
    matcher = ChainRequestMatcher([PathRequestMatcher(r"^/api"), MethodRequestMatcher(["POST"])])
    assert not matcher.matches(_request("/api/books", "GET"))


def test_an_empty_chain_claims_everything() -> None:
    assert ChainRequestMatcher([]).matches(_request("/anything", "GET"))
