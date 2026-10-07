"""The JWT bundle wires its services and refuses an unsigned configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_dependency_injection import Kernel, env
from xtr_security.bundle import InvalidConfigurationError
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.bundle.encoder_config import EncoderConfig
from xtr_security_jwt.bundle.jwt_bundle import JwtBundle
from xtr_security_jwt.bundle.jwt_config import JwtConfig

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

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
    assert "issuer" in message
    assert "config/jwt.py" in message


def test_it_accepts_a_configuration_with_a_signing_key_and_issuer() -> None:
    JwtBundle._require_build_settings(JwtConfig(secret_key="pem", issuer="issuer-a"))


def test_a_configuration_with_a_key_but_no_issuer_is_refused_naming_the_issuer() -> None:
    with pytest.raises(InvalidConfigurationError) as info:
        JwtBundle._require_build_settings(JwtConfig(secret_key="pem"))

    assert "issuer" in str(info.value)


def test_a_configuration_whose_signing_key_is_empty_is_refused_naming_the_key() -> None:
    # An empty string is no more a signing key than None is: it would reach the
    # key loader as key material and fail far from the configuration.
    with pytest.raises(InvalidConfigurationError) as info:
        JwtBundle._require_build_settings(JwtConfig(secret_key="", issuer="issuer-a"))

    assert "signing key" in str(info.value)


def _hmac(secret: str, algorithm: str = "HS256") -> JwtConfig:
    """Return a buildable configuration signing with ``algorithm`` over ``secret``."""
    return JwtConfig(
        secret_key=secret,
        issuer="https://jwt.test",
        encoder=EncoderConfig(signature_algorithm=algorithm),
    )


def test_building_a_kernel_with_a_short_hmac_secret_fails_naming_the_algorithm() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_short_secret_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    with pytest.raises(InvalidConfigurationError) as info:
        _ = kernel.build()

    message = str(info.value)
    assert "HS256" in message
    assert "32 bytes" in message


def test_a_short_hmac_secret_given_inline_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="32 bytes"):
        JwtBundle._require_hmac_secret_length(_hmac("short"))


def test_a_long_enough_hmac_secret_given_inline_is_accepted() -> None:
    JwtBundle._require_hmac_secret_length(_hmac("a" * 32))


def test_a_short_path_naming_a_file_of_a_long_secret_is_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # One byte of path for 32 bytes of secret: measuring the configured string
    # would refuse what the key loader reads.
    _ = (tmp_path / "s").write_text("a" * 32, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    JwtBundle._require_hmac_secret_length(_hmac("s"))


def test_a_long_path_naming_a_file_of_a_short_secret_is_refused(tmp_path: Path) -> None:
    secret_file = tmp_path / ("a_path_far_longer_than_the_secret_it_names" * 2)
    _ = secret_file.write_text("short", encoding="utf-8")

    with pytest.raises(InvalidConfigurationError, match="32 bytes"):
        JwtBundle._require_hmac_secret_length(_hmac(str(secret_file)))


def test_a_non_hmac_algorithm_has_no_secret_floor() -> None:
    JwtBundle._require_hmac_secret_length(_hmac("short", "RS256"))


def test_an_unresolved_env_placeholder_is_left_for_the_provider_to_measure() -> None:
    # The build does not resolve env(), so the placeholder holds the expression
    # rather than the deployment's secret: there is nothing to measure yet, and
    # reading it as key material would fail on a value that is not a path.
    JwtBundle._require_hmac_secret_length(_hmac(env("JWT_SECRET")))


def test_building_a_kernel_whose_extractors_are_all_disabled_fails_naming_the_config() -> None:
    kernel = Kernel(
        "tests.fixtures.jwt_no_extractor_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
    )

    with pytest.raises(InvalidArgumentError, match="TokenExtractorsConfig"):
        _ = kernel.build()
