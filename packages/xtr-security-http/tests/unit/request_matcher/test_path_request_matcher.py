"""The path matcher claims a request whose path matches its pattern."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.requests import make_request
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _request(path: str) -> Request:
    request = make_request()
    request.scope["path"] = path
    return request


def test_it_claims_a_matching_path() -> None:
    matcher = PathRequestMatcher(r"^/api")
    assert matcher.matches(_request("/api/books"))


def test_it_declines_a_non_matching_path() -> None:
    matcher = PathRequestMatcher(r"^/api")
    assert not matcher.matches(_request("/public"))


def test_a_bad_pattern_is_refused_where_written() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PathRequestMatcher(r"(")
