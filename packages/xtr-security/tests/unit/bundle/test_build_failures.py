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
