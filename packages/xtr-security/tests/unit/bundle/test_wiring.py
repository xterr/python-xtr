"""The wiring helpers register the security services they own, and no more.

A genuine unit test of the ``register_voters`` and ``register_hashers`` helpers:
each is driven against a recording configurator that captures every ``set`` and
``alias``, so the surface each helper contributes is asserted directly — the
voters are tagged, the hasher factory and user hasher are aliased, and neither
helper registers the role hierarchy the bundle owns. The end-to-end wiring is
driven by the integration suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_password_hasher import PasswordHasherFactoryInterface, UserPasswordHasherInterface
from xtr_security_core import RoleHierarchyInterface
from xtr_security_http import AccessMap, AuthenticatorManager, ExposeSecurityLevel

from xtr_security.bundle import AutoHasherConfig, NativeHasherConfig, SecurityConfig
from xtr_security.bundle._wiring import (
    DUMMY_PASSWORD_HASHER_QUALIFIER,
    VOTER_TAG,
    _default_hasher_config,
    _register_context_factory,
    register_hashers,
    register_voters,
)
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.firewall_config import FirewallConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_password_hasher import PasswordHasherInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingDefinition:
    """A stand-in definition recording the tags a helper adds to a service."""

    def __init__(self, tags: list[str]) -> None:
        self._tags: list[str] = tags

    def add_tag(self, name: str, **attributes: object) -> _RecordingDefinition:
        del attributes
        self._tags.append(name)
        return self


@final
class _RecordingConfigurator:
    """A configurator recording every ``set`` target and ``alias`` a helper makes."""

    def __init__(self) -> None:
        self.set_targets: list[object] = []
        self.by_qualifier: dict[Hashable, object] = {}
        self.aliases: list[type] = []
        self.tags: list[str] = []

    def set(
        self,
        target: type | Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> _RecordingDefinition:
        del lifetime
        self.set_targets.append(target)
        if qualifier is not None:
            self.by_qualifier[qualifier] = target
        return _RecordingDefinition(self.tags)

    def alias(
        self,
        alias: type,
        target: type,
        /,
        *,
        alias_qualifier: Hashable | None = None,
        target_qualifier: Hashable | None = None,
    ) -> None:
        del target, alias_qualifier, target_qualifier
        self.aliases.append(alias)


def test_the_voter_tag_is_named() -> None:
    assert VOTER_TAG == "security.voter"


def test_register_voters_tags_every_built_in_voter() -> None:
    services = _RecordingConfigurator()

    register_voters(cast("ServiceConfigurator", cast("object", services)))

    assert services.tags == [VOTER_TAG, VOTER_TAG, VOTER_TAG, VOTER_TAG]


def test_register_hashers_aliases_the_factory_and_the_user_hasher() -> None:
    services = _RecordingConfigurator()

    register_hashers(cast("ServiceConfigurator", cast("object", services)), SecurityConfig())

    assert PasswordHasherFactoryInterface in services.aliases
    assert UserPasswordHasherInterface in services.aliases


def test_the_role_hierarchy_is_not_registered_by_the_helpers() -> None:
    services = _RecordingConfigurator()

    register_voters(cast("ServiceConfigurator", cast("object", services)))
    register_hashers(cast("ServiceConfigurator", cast("object", services)), SecurityConfig())

    assert RoleHierarchyInterface not in services.aliases
    assert RoleHierarchyInterface not in services.set_targets


@final
class _EmptyLocator:
    """A service locator a context factory with no authenticators never queries."""

    async def get(self, name: object) -> object:  # pragma: no cover -- never called
        raise AssertionError(name)


async def test_the_configured_expose_level_reaches_the_manager() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(pattern=r"^/api", security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )
    factory = cast("Callable[..., Awaitable[FirewallContext]]", services.set_targets[-1])

    context = await factory(
        storage=object(),
        dispatcher=object(),
        decision_manager=object(),
        authenticators=_EmptyLocator(),
    )
    manager = cast("AuthenticatorManager", context.authenticator_manager)

    assert manager._expose_security_errors is ExposeSecurityLevel.ALL


def test_the_default_hasher_config_is_the_first_configured_one() -> None:
    config = SecurityConfig(password_hashers={"users": NativeHasherConfig(algorithm="bcrypt")})

    assert _default_hasher_config(config) == NativeHasherConfig(algorithm="bcrypt")


def test_the_default_hasher_config_falls_back_to_auto() -> None:
    assert _default_hasher_config(SecurityConfig()) == AutoHasherConfig()


def test_the_registered_dummy_hasher_builds_the_configured_kind() -> None:
    services = _RecordingConfigurator()
    config = SecurityConfig(password_hashers={"users": NativeHasherConfig(algorithm="bcrypt")})

    register_hashers(cast("ServiceConfigurator", cast("object", services)), config)
    factory = cast(
        "Callable[[], PasswordHasherInterface]",
        services.by_qualifier[DUMMY_PASSWORD_HASHER_QUALIFIER],
    )

    assert factory().hash("secret").startswith("$2b$")


def test_the_registered_dummy_hasher_falls_back_to_the_secure_default() -> None:
    services = _RecordingConfigurator()

    register_hashers(cast("ServiceConfigurator", cast("object", services)), SecurityConfig())
    factory = cast(
        "Callable[[], PasswordHasherInterface]",
        services.by_qualifier[DUMMY_PASSWORD_HASHER_QUALIFIER],
    )

    assert factory().hash("secret").startswith("$")
