"""The firewall scheme's OpenAPI properties, read through the active registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi.security import HTTPBearer
from fastapi.security.base import SecurityBase

from xtr_security_http.exception import FirewallNotBootedError
from xtr_security_http.firewall_scheme import FirewallScheme
from xtr_security_http.firewall_scheme_registry import (
    FirewallSchemeRegistry,
    active_firewall_schemes,
)

if TYPE_CHECKING:
    from fastapi.openapi.models import SecurityBase as SecurityBaseModel


def _model() -> SecurityBaseModel:
    return HTTPBearer(auto_error=False, bearerFormat="JWT").model


def test_a_scheme_is_a_security_base() -> None:
    assert isinstance(FirewallScheme("api"), SecurityBase)


def test_an_unbound_scheme_is_a_generic_bearer() -> None:
    scheme = FirewallScheme(None)

    assert scheme.scheme_name == "firewall"
    assert scheme.model is not None


def test_a_bound_scheme_reads_the_active_registry() -> None:
    registry = FirewallSchemeRegistry()
    registry.register("api", _model(), "api")
    scheme = FirewallScheme("api")

    with active_firewall_schemes(registry):
        assert scheme.scheme_name == "api"
        assert scheme.model is not None


def test_a_bound_scheme_without_a_registry_fails_loudly() -> None:
    scheme = FirewallScheme("api")

    with pytest.raises(FirewallNotBootedError):
        _ = scheme.model


def test_a_bound_scheme_name_without_a_registry_fails_loudly() -> None:
    scheme = FirewallScheme("api")

    with pytest.raises(FirewallNotBootedError):
        _ = scheme.scheme_name
