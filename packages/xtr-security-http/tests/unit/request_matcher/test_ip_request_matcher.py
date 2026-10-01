"""The address matcher claims a request by its client address."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.requests import make_request
from xtr_security_http.request_matcher.ip_request_matcher import IpRequestMatcher

if TYPE_CHECKING:
    from starlette.requests import Request


def _request(client: tuple[str, int] | None) -> Request:
    request = make_request()
    if client is None:
        request.scope.pop("client", None)
    else:
        request.scope["client"] = client
    return request


def test_it_claims_a_listed_address() -> None:
    matcher = IpRequestMatcher(["10.0.0.1", "10.0.0.2"])
    assert matcher.matches(_request(("10.0.0.1", 5000)))


def test_it_declines_an_unlisted_address() -> None:
    matcher = IpRequestMatcher(["10.0.0.1"])
    assert not matcher.matches(_request(("192.168.0.1", 5000)))


def test_a_request_with_no_client_is_never_claimed() -> None:
    matcher = IpRequestMatcher(["10.0.0.1"])
    assert not matcher.matches(_request(None))
