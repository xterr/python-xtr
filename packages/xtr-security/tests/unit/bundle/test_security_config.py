"""The security configuration builds a working nothing and cross-checks itself."""

from __future__ import annotations

from importlib.util import find_spec

import pytest

from xtr_security.bundle import (
    AccessTokenConfig,
    ChainUserProviderConfig,
    FirewallConfig,
    NativeHasherConfig,
    Pbkdf2HasherConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    ServiceUserProviderConfig,
)
from xtr_security.exception import InvalidConfigurationError

_OIDC_AVAILABLE = find_spec("joserfc") is not None and find_spec("httpx") is not None


class _Provider:
    """A stand-in provider class for a service user provider config."""


class _Handler:
    """A stand-in handler class for a service token handler config."""


def _access_token() -> AccessTokenConfig:
    return AccessTokenConfig(token_handler=ServiceTokenHandlerConfig(_Handler))


def test_zero_config_gives_no_firewalls_and_the_built_in_factories() -> None:
    config = SecurityConfig()

    assert config.firewalls == {}
    assert len(config.authenticator_factories) == 1
    assert len(config.user_provider_factories) == 3
    keys = {factory.key for factory in config.token_handler_factories}
    assert "id" in keys


def test_the_oidc_factory_joins_the_defaults_when_its_extra_is_installed() -> None:
    config = SecurityConfig()
    keys = {factory.key for factory in config.token_handler_factories}

    if _OIDC_AVAILABLE:
        assert "oidc" in keys
    else:
        assert "oidc" not in keys


def test_zero_config_defaults_to_the_affirmative_strategy() -> None:
    assert SecurityConfig().access_decision_manager.strategy == "affirmative"


def test_a_firewall_may_name_a_declared_provider() -> None:
    config = SecurityConfig(
        providers={"users": ServiceUserProviderConfig(_Provider)},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api", provider="users", authenticators=(_access_token(),)
            )
        },
    )

    assert "api" in config.firewalls


def test_an_unknown_provider_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = SecurityConfig(
            firewalls={
                "api": FirewallConfig(
                    pattern=r"^/api",
                    provider="missing",
                    authenticators=(_access_token(),),
                )
            },
        )


def test_a_chain_naming_an_undeclared_provider_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = SecurityConfig(
            providers={
                "users": ServiceUserProviderConfig(_Provider),
                "chain": ChainUserProviderConfig(providers=("users", "missing")),
            },
        )


def test_a_chain_naming_only_declared_providers_is_accepted() -> None:
    config = SecurityConfig(
        providers={
            "users": ServiceUserProviderConfig(_Provider),
            "chain": ChainUserProviderConfig(providers=("users",)),
        },
    )

    assert "chain" in config.providers


def test_a_top_level_pbkdf2_hasher_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = SecurityConfig(password_hashers={"legacy": Pbkdf2HasherConfig()})


def test_a_pbkdf2_hasher_inside_migrate_from_is_accepted() -> None:
    config = SecurityConfig(
        password_hashers={"users": NativeHasherConfig(migrate_from=(Pbkdf2HasherConfig(),))},
    )

    assert "users" in config.password_hashers
