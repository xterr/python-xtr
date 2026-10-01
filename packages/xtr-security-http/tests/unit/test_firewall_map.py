"""The firewall map finds firewalls by name and by request matcher."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.contexts import FakeFirewallContext
from tests.support.requests import make_request
from xtr_security_http.exception import UnknownFirewallError
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.request_matcher.chain_request_matcher import ChainRequestMatcher
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase


def _context(name: str, *, security: bool = True) -> FakeFirewallContext:
    from fastapi.security import HTTPBearer  # noqa: PLC0415

    scheme: SecurityBase = HTTPBearer(auto_error=False)
    return FakeFirewallContext(
        name=name,
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        dispatcher=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=scheme,
        security=security,
    )


def _anything() -> ChainRequestMatcher:
    return ChainRequestMatcher(())


def test_it_finds_a_firewall_by_name() -> None:
    context = _context("api")
    firewall_map = FirewallMap(((_anything(), context),))

    assert firewall_map.has("api") is True
    assert firewall_map.get("api") is context
    assert firewall_map.names() == ("api",)


def test_an_unknown_name_is_refused() -> None:
    firewall_map = FirewallMap(((_anything(), _context("api")),))

    with pytest.raises(UnknownFirewallError):
        _ = firewall_map.get("missing")


def test_duplicate_names_are_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = FirewallMap(
            (
                (_anything(), _context("api")),
                (_anything(), _context("api")),
            ),
        )


def test_it_matches_the_first_firewall_that_claims_the_request() -> None:
    admin = _context("admin")
    api = _context("api")
    firewall_map = FirewallMap(
        (
            (PathRequestMatcher(r"^/admin"), admin),
            (PathRequestMatcher(r"^/api"), api),
        ),
    )

    request = make_request()
    request.scope["path"] = "/api/books"

    assert firewall_map.match(request) is api


def test_no_match_returns_none() -> None:
    firewall_map = FirewallMap(((PathRequestMatcher(r"^/api"), _context("api")),))
    request = make_request()
    request.scope["path"] = "/public"

    assert firewall_map.match(request) is None
