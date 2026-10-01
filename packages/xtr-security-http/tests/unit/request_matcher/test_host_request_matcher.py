"""The host matcher claims a request by its host, waiving a hostless one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.requests import make_request
from xtr_security_http.request_matcher.host_request_matcher import HostRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _request(host: str | None) -> Request:
    request = make_request(headers={"host": host} if host is not None else None)
    request.scope["path"] = "/"
    return request


def test_it_claims_a_matching_host() -> None:
    matcher = HostRequestMatcher(r"^api\.example\.com$")
    assert matcher.matches(_request("api.example.com"))


def test_it_declines_a_non_matching_host() -> None:
    matcher = HostRequestMatcher(r"^api\.example\.com$")
    assert not matcher.matches(_request("other.example.com"))


def test_a_hostless_request_is_claimed() -> None:
    matcher = HostRequestMatcher(r"^api\.example\.com$")
    assert matcher.matches(_request(None))


def test_a_bad_pattern_is_refused_where_written() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = HostRequestMatcher(r"(")
