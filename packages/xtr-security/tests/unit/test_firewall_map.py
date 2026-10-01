"""The bundle's firewall map finds, matches, and reads a firewall's config."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.security import HTTPBearer
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http.exception import UnknownFirewallError
from xtr_security_http.firewall_map_interface import FirewallMapInterface

from tests.support.requests import make_request
from xtr_security.firewall_config import FirewallConfig
from xtr_security.firewall_context import FirewallContext
from xtr_security.firewall_map import FirewallEntry, FirewallMap

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface


def _context(name: str) -> FirewallContext:
    scheme: SecurityBase = HTTPBearer(auto_error=False)
    return FirewallContext(
        name=name,
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        dispatcher=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=scheme,
    )


def _entry(name: str, matcher: RequestMatcherInterface, config: FirewallConfig) -> FirewallEntry:
    return (matcher, _context(name), config)


def _request(path: str) -> object:
    request = make_request()
    request.scope["path"] = path
    return request


def test_it_implements_the_http_firewall_map_interface() -> None:
    assert FirewallMapInterface in FirewallMap.__mro__


def test_it_finds_a_firewall_by_name() -> None:
    config = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap((_entry("api", config.to_matcher(), config),))

    assert firewall_map.has("api") is True
    assert firewall_map.get("api").name == "api"
    assert firewall_map.names() == ("api",)


def test_an_unknown_name_is_refused() -> None:
    config = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap((_entry("api", config.to_matcher(), config),))

    with pytest.raises(UnknownFirewallError):
        _ = firewall_map.get("missing")


def test_duplicate_names_are_refused() -> None:
    config = FirewallConfig(pattern=r"^/api", security=False)
    with pytest.raises(InvalidArgumentError):
        _ = FirewallMap(
            (
                _entry("api", config.to_matcher(), config),
                _entry("api", config.to_matcher(), config),
            ),
        )


def test_it_matches_the_first_firewall_that_claims_the_request() -> None:
    admin = FirewallConfig(pattern=r"^/admin", security=False)
    api = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap(
        (
            _entry("admin", admin.to_matcher(), admin),
            _entry("api", api.to_matcher(), api),
        ),
    )

    matched = firewall_map.match(_request("/api/books"))  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    assert matched is not None
    assert matched.name == "api"


def test_no_match_returns_none() -> None:
    config = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap((_entry("api", config.to_matcher(), config),))

    assert firewall_map.match(_request("/public")) is None  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_it_reads_the_config_of_the_firewall_that_claims_the_request() -> None:
    api = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap((_entry("api", api.to_matcher(), api),))

    assert firewall_map.get_firewall_config(_request("/api/books")) is api  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_no_claiming_firewall_reads_no_config() -> None:
    api = FirewallConfig(pattern=r"^/api", security=False)
    firewall_map = FirewallMap((_entry("api", api.to_matcher(), api),))

    assert firewall_map.get_firewall_config(_request("/public")) is None  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_an_empty_map_matches_nothing() -> None:
    firewall_map = FirewallMap()

    assert firewall_map.names() == ()
    assert firewall_map.match(_request("/api")) is None  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    assert firewall_map.get_firewall_config(_request("/api")) is None  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
