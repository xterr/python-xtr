"""The JWT bundle builds and boots unconfigured, and reports a missing key where it is needed."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_security.bundle import InvalidConfigurationError
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_jwt.bundle.jwt_bundle import JwtBundle
from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
from xtr_security_jwt.exception import MissingKeyError
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface

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


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(JwtBundle)


def _unconfigured() -> Kernel:
    return Kernel(
        "tests.fixtures.jwt_unconfigured_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )


async def test_signing_without_a_key_raises_the_missing_key_naming_what_to_set() -> None:
    async with await _unconfigured().boot() as booted:
        manager = await booted.container.get(JwtTokenManagerInterface)

        with pytest.raises(MissingKeyError, match=r"config/jwt\.py.*jwt:generate-keypair"):
            _ = await manager.create(InMemoryUser("ada", roles=["ROLE_USER"]))


async def test_verifying_without_a_key_raises_the_missing_key_not_a_token_failure() -> None:
    # A deployment's missing key is not the client's bad token: it must not read as a 401.
    async with await _unconfigured().boot() as booted:
        encoder = await booted.container.get(JwtEncoderInterface)

        with pytest.raises(MissingKeyError):
            _ = encoder.decode("eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZGEifQ.c2ln")


async def test_a_short_hmac_secret_builds_and_is_refused_when_it_first_signs() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_short_secret_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    async with await kernel.boot() as booted:
        encoder = await booted.container.get(JwtEncoderInterface)

        with pytest.raises(InvalidConfigurationError, match=r"HS256.*32 bytes"):
            _ = encoder.encode({"sub": "ada"})


async def test_a_token_is_stamped_with_the_kernels_name_when_no_issuer_is_set() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_default_issuer_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    async with await kernel.boot() as booted:
        manager = await booted.container.get(JwtTokenManagerInterface)
        claims = await manager.parse(await manager.create(InMemoryUser("ada", roles=[])))

    assert claims["iss"] == "jwt_default_issuer_app"


def test_building_a_kernel_whose_extractors_are_all_disabled_fails_naming_the_config() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_no_extractor_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    with pytest.raises(InvalidArgumentError, match="TokenExtractorsConfig"):
        _ = kernel.build()
