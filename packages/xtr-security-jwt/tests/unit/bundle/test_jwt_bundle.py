"""The JWT bundle wires its services and refuses an unsigned configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_security.bundle import InvalidConfigurationError

from xtr_security_jwt.bundle.jwt_bundle import JwtBundle
from xtr_security_jwt.bundle.jwt_config import JwtConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection.bundle import BundleMetadata, RequiredBundle

pytestmark = pytest.mark.anyio


def test_the_bundle_is_named_jwt() -> None:
    metadata = cast("BundleMetadata", getattr(JwtBundle, "__xtr_bundle__"))  # noqa: B009

    assert metadata.name == "jwt"


def test_it_requires_the_security_and_clock_bundles() -> None:
    required = cast(
        "Sequence[RequiredBundle]",
        getattr(JwtBundle, "__xtr_required_bundles__"),  # noqa: B009
    )
    targets = {one.target for one in required}

    assert "xtr_security.bundle:SecurityBundle" in targets
    assert "xtr_clock.bundle:ClockBundle" in targets
    assert "xtr_event_dispatcher.bundle:EventDispatcherBundle" in targets


def test_building_a_kernel_with_no_signing_key_fails_naming_the_config() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_unconfigured_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    with pytest.raises(InvalidConfigurationError) as info:
        _ = kernel.build()

    message = str(info.value)
    assert "signing key" in message
    assert "config/jwt.py" in message


def test_it_accepts_a_configuration_with_a_signing_key() -> None:
    JwtBundle._require_secret_key(JwtConfig(secret_key="pem"))
