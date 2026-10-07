"""The firewall scheme registry and the active-registry holder it is read through."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.security import HTTPBearer

from xtr_security_http.firewall_scheme_registry import (
    FirewallSchemeRegistry,
    active_firewall_scheme_registry,
    active_firewall_schemes,
)

if TYPE_CHECKING:
    from fastapi.openapi.models import SecurityBase as SecurityBaseModel


def _model() -> SecurityBaseModel:
    return HTTPBearer(auto_error=False, bearerFormat="JWT").model


def test_the_registry_records_and_reads_a_scheme() -> None:
    registry = FirewallSchemeRegistry()
    registry.register("api", _model(), "api")

    entry = registry.get("api")
    assert entry is not None
    assert entry.scheme_name == "api"


def test_the_registry_returns_none_for_an_unknown_firewall() -> None:
    assert FirewallSchemeRegistry().get("api") is None


def test_no_registry_is_active_outside_a_block() -> None:
    assert active_firewall_scheme_registry() is None


def test_a_block_makes_its_registry_the_active_one() -> None:
    registry = FirewallSchemeRegistry()

    with active_firewall_schemes(registry):
        assert active_firewall_scheme_registry() is registry


def test_the_previous_registry_is_restored_on_exit() -> None:
    registry = FirewallSchemeRegistry()

    with active_firewall_schemes(registry):
        pass

    assert active_firewall_scheme_registry() is None
