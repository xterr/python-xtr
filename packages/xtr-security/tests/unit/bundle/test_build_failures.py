"""A configuration a per-field check cannot catch fails when the build runs."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from xtr_security.bundle import SecurityBundle
from xtr_security.exception import InvalidConfigurationError

pytestmark = pytest.mark.anyio


async def test_an_authenticator_with_no_factory_fails_the_build() -> None:
    kernel = Kernel(
        "tests.fixtures.broken_apps.missing_factory",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError):
        _ = kernel.build()


async def test_an_ambiguous_entry_point_fails_the_build() -> None:
    from tests.fixtures.broken_apps.ambiguous_entry_point.config import AmbiguousBundle

    kernel = Kernel(
        "tests.fixtures.broken_apps.ambiguous_entry_point",
        env="test",
        bundles={AmbiguousBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError):
        _ = kernel.build()


async def test_a_stateful_firewall_without_a_session_storage_fails_the_build() -> None:
    kernel = Kernel(
        "tests.fixtures.broken_apps.stateful_without_storage",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError, match="SessionStorageInterface"):
        _ = kernel.build()


async def test_a_form_login_on_a_stateless_firewall_fails_the_build() -> None:
    kernel = Kernel(
        "tests.fixtures.broken_apps.form_login_on_stateless",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError, match="form login"):
        _ = kernel.build()


async def test_a_logout_asking_for_a_csrf_check_on_a_stateless_firewall_fails_the_build() -> None:
    kernel = Kernel(
        "tests.fixtures.broken_apps.logout_csrf_on_stateless",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError, match="cross-site request forgery"):
        _ = kernel.build()


async def test_csrf_route_markers_on_a_stateless_firewall_fail_the_build() -> None:
    kernel = Kernel(
        "tests.fixtures.broken_apps.csrf_route_markers_on_stateless",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    with pytest.raises(InvalidConfigurationError, match="cross-site request forgery"):
        _ = kernel.build()
