"""An access-control configuration validates and builds the request matcher."""

from __future__ import annotations

import re

import pytest
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface

from tests.support.requests import make_request
from xtr_security.bundle import AccessControlConfig


def test_it_builds_a_request_matcher() -> None:
    config = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", methods=("get",))
    matcher = config.to_matcher()

    assert isinstance(matcher, RequestMatcherInterface)


def test_the_built_matcher_claims_a_matching_request() -> None:
    config = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", methods=("GET",))
    matcher = config.to_matcher()

    request = make_request(method="GET")
    request.scope["path"] = "/api/books"

    assert matcher.matches(request)


def test_the_built_matcher_declines_a_non_matching_method() -> None:
    config = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", methods=("POST",))
    matcher = config.to_matcher()

    request = make_request(method="GET")
    request.scope["path"] = "/api/books"

    assert not matcher.matches(request)


def test_an_empty_attribute_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AccessControlConfig(path=r"^/api", attribute="")


def test_a_bad_pattern_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AccessControlConfig(path=r"^/(api", attribute="ROLE_USER")


def test_a_cidr_entry_is_accepted() -> None:
    config = AccessControlConfig(
        path=r"^/api",
        attribute="ROLE_USER",
        ips=("10.0.0.0/8", "::1", "192.168.1.7/24"),
    )

    assert config.ips == ("10.0.0.0/8", "::1", "192.168.1.7/24")


def test_a_bad_address_entry_is_refused_by_name() -> None:
    with pytest.raises(InvalidArgumentError, match="not-an-address"):
        _ = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", ips=("not-an-address",))


def test_an_out_of_range_address_entry_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape("10.0.0.300")):
        _ = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", ips=("10.0.0.300",))


def test_an_empty_method_entry_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="method"):
        _ = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", methods=("",))


def test_a_method_entry_with_a_separator_is_refused_by_name() -> None:
    with pytest.raises(InvalidArgumentError, match="GET POST"):
        _ = AccessControlConfig(path=r"^/api", attribute="ROLE_USER", methods=("GET POST",))
