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
from typing_extensions import override
from xtr_password_hasher import PasswordHasherFactoryInterface, UserPasswordHasherInterface
from xtr_security_core import MissingUserProvider, RoleHierarchyInterface, UserProviderInterface
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http import (
    AccessListener,
    AccessMap,
    AuthenticatorManager,
    ExposeSecurityLevel,
    FirewallListenerInterface,
)
from xtr_security_http.firewall.exception_listener import ExceptionListener

from xtr_security.bundle import (
    AutoHasherConfig,
    InMemoryUserProviderConfig,
    NativeHasherConfig,
    SecurityConfig,
    firewall_access_listener_name,
    firewall_manager_listener_name,
)
from xtr_security.bundle._wiring import (
    DUMMY_PASSWORD_HASHER_QUALIFIER,
    VOTER_TAG,
    _default_hasher_config,
    _register_authenticators,
    _register_context_factory,
    register_hashers,
    register_voters,
)
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.factory import (
    AuthenticatorFactoryInterface,
    StatelessAuthenticatorFactoryInterface,
)
from xtr_security.firewall_config import FirewallConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable, Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_password_hasher import PasswordHasherInterface

pytestmark = pytest.mark.anyio


@final
class _RecordingDefinition:
    """A stand-in definition recording the tags and arguments a helper gives a service."""

    def __init__(self, tags: list[str]) -> None:
        self._tags: list[str] = tags
        self.arguments: dict[str, object] = {}

    def add_tag(self, name: str, **attributes: object) -> _RecordingDefinition:
        del attributes
        self._tags.append(name)
        return self

    def set_argument(self, name: str, value: object, /) -> _RecordingDefinition:
        self.arguments[name] = value
        return self


@final
class _RecordingConfigurator:
    """A configurator recording every ``set`` target and ``alias`` a helper makes."""

    def __init__(self) -> None:
        self.set_targets: list[object] = []
        self.by_qualifier: dict[Hashable, object] = {}
        self.aliases: list[type] = []
        self.tags: list[str] = []
        self.definitions: list[_RecordingDefinition] = []

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
        definition = _RecordingDefinition(self.tags)
        self.definitions.append(definition)
        return definition

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


@final
class _ChainLocator:
    """A service locator answering each chain qualifier with a stand-in listener."""

    async def get(self, name: object) -> object:
        return f"listener:{name}"


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
    factory = cast("Callable[..., Awaitable[AuthenticatorManager]]", services.set_targets[0])

    manager = await factory(
        storage=object(),
        dispatcher=object(),
        authenticators=_EmptyLocator(),
    )

    assert manager._expose_security_errors is ExposeSecurityLevel.ALL


def test_the_manager_listener_is_registered_and_aliased_into_the_chain() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )

    assert services.by_qualifier[firewall_manager_listener_name("api")] is services.set_targets[1]
    assert services.aliases == [FirewallListenerInterface, FirewallListenerInterface]


def test_the_access_listener_is_registered_and_aliased_into_the_chain() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )

    assert services.by_qualifier[firewall_access_listener_name("api")] is services.set_targets[2]


async def test_the_access_listener_is_built_over_the_storage_the_decider_and_the_map() -> None:
    services = _RecordingConfigurator()
    access_map = AccessMap()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=access_map,
        expose=ExposeSecurityLevel.ALL,
    )
    factory = cast("Callable[..., Awaitable[AccessListener]]", services.set_targets[2])

    storage = TokenStorage()
    decision_manager = AccessDecisionManager([])
    listener = await factory(storage=storage, decision_manager=decision_manager)

    assert isinstance(listener, AccessListener)
    assert listener._token_storage is storage
    assert listener._access_decision_manager is decision_manager
    assert listener._access_map is access_map


def test_the_context_factory_parks_the_chain_on_the_listeners_argument() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False, listeners=("late", "early")),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )

    assert services.definitions[-1].arguments == {
        "listeners": (
            firewall_manager_listener_name("api"),
            firewall_access_listener_name("api"),
            "late",
            "early",
        )
    }


async def test_the_context_factory_resolves_the_parked_chain_through_the_locator() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False, listeners=("late", "early")),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )
    factory = cast("Callable[..., Awaitable[FirewallContext]]", services.set_targets[-1])
    exception_listener = cast("ExceptionListener", object())

    context = await factory(
        manager=cast("AuthenticatorManager", object()),
        access_listener=cast("AccessListener", object()),
        authenticators=_EmptyLocator(),
        responses=object(),
        chain=_ChainLocator(),
        exception_listener=exception_listener,
        listeners=("early", "late"),
    )

    assert context.listeners == ("listener:early", "listener:late")
    assert context.exception_listener is exception_listener
    assert context.logout_listener is None


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


@final
class _NeedyConfig:
    """The configuration of an authenticator that needs a user provider."""


@final
class _StatelessConfig:
    """The configuration of an authenticator that can do without one."""


class _RecordingFactory(AuthenticatorFactoryInterface):
    """An authenticator factory recording the user provider it was handed."""

    _config_type: type
    user_providers: list[ServiceKey | None]

    def __init__(self, config_type: type) -> None:
        self._config_type = config_type
        self.user_providers = []

    @property
    @override
    def key(self) -> str:
        return self._config_type.__name__

    @property
    @override
    def priority(self) -> int:
        return 0

    @property
    @override
    def config_type(self) -> type:
        return self._config_type

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        del services, builder, firewall_name, config
        self.user_providers.append(user_provider)
        return ()


@final
class _StatelessRecordingFactory(_RecordingFactory, StatelessAuthenticatorFactoryInterface):
    """A stateless recording factory: its authenticator can do without a provider."""


def _register(
    config: SecurityConfig, firewall: FirewallConfig
) -> tuple[_RecordingConfigurator, _RecordingFactory, _RecordingFactory]:
    needy = _RecordingFactory(_NeedyConfig)
    stateless = _StatelessRecordingFactory(_StatelessConfig)
    services = _RecordingConfigurator()
    configured = SecurityConfig(
        providers=config.providers,
        authenticator_factories=(needy, stateless),
    )
    _ = _register_authenticators(
        cast("ServiceConfigurator", cast("object", services)),
        configured,
        "api",
        firewall,
        firewall.provider,
    )
    return services, needy, stateless


def test_with_no_provider_anywhere_a_needy_authenticator_gets_the_missing_provider() -> None:
    firewall = FirewallConfig(authenticators=(_NeedyConfig(), _StatelessConfig()))

    services, needy, stateless = _register(SecurityConfig(), firewall)

    qualifier = "security.user.provider.missing.api"
    assert needy.user_providers == [(UserProviderInterface, qualifier)]
    assert stateless.user_providers == [None]
    factory = cast("Callable[[], MissingUserProvider]", services.by_qualifier[qualifier])
    with pytest.raises(InvalidArgumentError, match='"api" firewall requires a user provider'):
        _ = factory()


def test_with_a_provider_configured_elsewhere_no_missing_provider_is_registered() -> None:
    config = SecurityConfig(providers={"users": InMemoryUserProviderConfig()})
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    services, needy, _ = _register(config, firewall)

    assert needy.user_providers == [None]
    assert MissingUserProvider not in services.aliases
    assert "security.user.provider.missing.api" not in services.by_qualifier


def test_the_firewall_provider_is_handed_to_every_authenticator() -> None:
    config = SecurityConfig(providers={"users": InMemoryUserProviderConfig()})
    firewall = FirewallConfig(provider="users", authenticators=(_NeedyConfig(), _StatelessConfig()))

    _, needy, stateless = _register(config, firewall)

    assert needy.user_providers == [(UserProviderInterface, "users")]
    assert stateless.user_providers == [(UserProviderInterface, "users")]
