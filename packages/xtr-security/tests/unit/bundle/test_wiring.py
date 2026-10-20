"""The wiring helpers register the security services they own, and no more.

A genuine unit test of the ``register_voters`` and ``register_hashers`` helpers:
each is driven against a recording configurator that captures every ``set`` and
``alias``, so the surface each helper contributes is asserted directly — the
voters are tagged, the hasher factory and user hasher are aliased, and neither
helper registers the role hierarchy the bundle owns. The end-to-end wiring is
driven by the integration suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

import pytest
from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_password_hasher import PasswordHasherFactoryInterface, UserPasswordHasherInterface
from xtr_security_core import MissingUserProvider, RoleHierarchyInterface, UserProviderInterface
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http import (
    AccessListener,
    AccessMap,
    AuthenticatorManager,
    ExposeSecurityLevel,
    FirewallListenerInterface,
    LogoutListener,
    SenderConstraintInterface,
)
from xtr_security_http.firewall.exception_listener import ExceptionListener

from xtr_security.bundle import (
    AccessControlConfig,
    AccessTokenConfig,
    AutoHasherConfig,
    InMemoryUserProviderConfig,
    NativeHasherConfig,
    OidcBackChannelLogoutConfig,
    OidcLoginConfig,
    SecurityConfig,
    ServiceTokenHandlerConfig,
    firewall_access_listener_name,
    firewall_manager_listener_name,
)
from xtr_security.bundle._authenticator_wiring import (
    register_authenticators as _register_authenticators,
)
from xtr_security.bundle._context_wiring import (
    register_context_factory as _register_context_factory,
)
from xtr_security.bundle._entry_point_wiring import resolve_entry_point as _resolve_entry_point
from xtr_security.bundle._firewall_wiring import _build_firewall_context
from xtr_security.bundle._hasher_wiring import _default_hasher_config
from xtr_security.bundle._wiring import (
    DUMMY_PASSWORD_HASHER_QUALIFIER,
    VOTER_TAG,
    register_hashers,
    register_voters,
)
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import (
    AuthenticatorFactoryInterface,
    OidcLoginFactory,
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

    def __init__(self, tags: list[str], qualifier: Hashable | None) -> None:
        self._tags: list[str] = tags
        self._qualifier = qualifier
        self.arguments: dict[str, object] = {}

    @property
    def key(self) -> tuple[type, Hashable | None]:
        """The service key of the definition, as the container would hand it."""
        return (object, self._qualifier)

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
        definition = _RecordingDefinition(self.tags, qualifier)
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

    context = await factory(
        manager=cast("AuthenticatorManager", object()),
        access_listener=cast("AccessListener", object()),
        authenticators=_EmptyLocator(),
        responses=ResponseFactory(),
        storage=TokenStorage(),
        trust_resolver=AuthenticationTrustResolver(),
        bridge=StarletteHttpFactory(),
        chain=_ChainLocator(),
        listeners=("early", "late"),
    )

    assert context.listeners == ("listener:early", "listener:late")
    assert isinstance(context.exception_listener, ExceptionListener)
    assert context.logout_listener is None


async def test_the_context_factory_builds_each_firewalls_own_exception_listener() -> None:
    """Two firewalls answer their failures with two listeners, not a shared one."""
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
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "admin",
        FirewallConfig(security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.ALL,
    )

    def context_factory_of(firewall: str) -> Callable[..., Awaitable[FirewallContext]]:
        """Return the context factory registered for ``firewall``."""
        for target in services.set_targets:
            if getattr(target, "__name__", None) == f"firewall_context_{firewall}":
                return cast("Callable[..., Awaitable[FirewallContext]]", target)
        raise AssertionError(f"no context factory for {firewall!r}")

    api_factory = context_factory_of("api")
    admin_factory = context_factory_of("admin")

    async def context_of(factory: Callable[..., Awaitable[FirewallContext]]) -> FirewallContext:
        return await factory(
            manager=cast("AuthenticatorManager", object()),
            access_listener=cast("AccessListener", object()),
            authenticators=_EmptyLocator(),
            responses=ResponseFactory(),
            storage=TokenStorage(),
            trust_resolver=AuthenticationTrustResolver(),
            bridge=StarletteHttpFactory(),
            chain=_ChainLocator(),
        )

    api = await context_of(api_factory)
    admin = await context_of(admin_factory)

    assert isinstance(api.exception_listener, ExceptionListener)
    assert isinstance(admin.exception_listener, ExceptionListener)
    assert api.exception_listener is not admin.exception_listener


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


def _keys(*qualifiers: str) -> list[tuple[type, str]]:
    """Service keys for authenticators aliased under the given qualifiers."""
    return [(object, qualifier) for qualifier in qualifiers]


def test_a_fallback_entry_point_never_wins_over_a_real_one() -> None:
    config = SecurityConfig()
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    resolved = _resolve_entry_point(
        config,
        "api",
        firewall,
        _keys("bearer", "form"),
        ("q0", "q1"),
        ("fallback", "real"),
    )

    assert resolved == "q1"


def test_a_fallback_entry_point_answers_when_no_real_one_runs() -> None:
    config = SecurityConfig()
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    resolved = _resolve_entry_point(
        config,
        "api",
        firewall,
        _keys("bearer", "other"),
        ("q0", "q1"),
        ("fallback", "none"),
    )

    assert resolved == "q0"


def test_two_real_entry_points_stay_ambiguous() -> None:
    config = SecurityConfig(
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    with pytest.raises(InvalidConfigurationError):
        _ = _resolve_entry_point(
            config,
            "api",
            firewall,
            _keys("form", "json"),
            ("q0", "q1"),
            ("real", "real"),
        )


def test_a_configured_entry_point_must_be_one_of_the_authenticators() -> None:
    config = SecurityConfig()
    firewall = FirewallConfig(
        entry_point="elsewhere",
        authenticators=(_NeedyConfig(),),
    )

    with pytest.raises(InvalidConfigurationError):
        _ = _resolve_entry_point(
            config,
            "api",
            firewall,
            _keys("form"),
            ("q0",),
            ("real",),
        )


def test_no_challenging_authenticator_needs_a_named_entry_point() -> None:
    config = SecurityConfig(
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    with pytest.raises(InvalidConfigurationError):
        _ = _resolve_entry_point(
            config,
            "api",
            firewall,
            _keys("one", "two"),
            ("q0", "q1"),
            ("none", "none"),
        )


def test_a_configured_entry_point_names_the_authenticator_that_answers() -> None:
    config = SecurityConfig()
    firewall = FirewallConfig(
        entry_point="form",
        authenticators=(_NeedyConfig(),),
    )

    resolved = _resolve_entry_point(
        config,
        "api",
        firewall,
        _keys("form", "bearer"),
        ("q0", "q1"),
        ("real", "fallback"),
    )

    assert resolved == "q0"


def test_no_challenging_authenticator_and_no_auth_rule_leaves_the_first() -> None:
    config = SecurityConfig()
    firewall = FirewallConfig(authenticators=(_NeedyConfig(),))

    resolved = _resolve_entry_point(
        config,
        "api",
        firewall,
        _keys("one", "two"),
        ("q0", "q1"),
        ("none", "none"),
    )

    assert resolved == "q0"


def test_the_scope_denied_handler_reads_the_access_token_settings() -> None:
    """The WWW-Authenticate answer reuses the authenticator's metadata and constraint."""
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(
            security=False,
            scope_denied_handler=_Inner,
            authenticators=(
                AccessTokenConfig(
                    token_handler=ServiceTokenHandlerConfig(_Handler),
                    resource_metadata_uri="/.well-known/oauth-protected-resource",
                    sender_constraint="api.constraint",
                ),
            ),
        ),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.NONE,
    )
    factory = services.set_targets[-1]

    assert factory.__annotations__["scope_denied"] is _Inner
    assert (
        factory.__annotations__["scope_constraint"]
        == Annotated[SenderConstraintInterface, Target("api.constraint")]
    )


def test_the_context_factory_annotates_the_denied_handler_it_is_given() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False, access_denied_handler=_Handler),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.NONE,
    )
    factory = services.set_targets[-1]

    assert factory.__annotations__["denied"] is _Handler


def test_the_scope_denied_handler_builds_bare_without_the_settings() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.NONE,
    )
    factory = services.set_targets[-1]

    assert "scope_denied" not in factory.__annotations__
    assert "scope_constraint" not in factory.__annotations__


class _Inner:
    """A stand-in inner access-denied handler service."""


class _Handler:
    """A stand-in token-handler class the service token-handler config names."""


def test_the_context_factory_parks_the_extra_listeners_ahead_of_the_owns() -> None:
    services = _RecordingConfigurator()
    _register_context_factory(
        cast("ServiceConfigurator", cast("object", services)),
        "api",
        FirewallConfig(security=False, listeners=("late",)),
        auth_qualifiers=(),
        entry_point_qualifier=None,
        access_map=AccessMap(),
        expose=ExposeSecurityLevel.NONE,
        extra_listeners=("api#oidc_token_refresh_listener",),
    )

    assert services.definitions[-1].arguments == {
        "listeners": (
            firewall_manager_listener_name("api"),
            firewall_access_listener_name("api"),
            "api#oidc_token_refresh_listener",
            "late",
        )
    }


def test_an_oidc_login_firewall_parks_its_refresh_listener_in_the_chain() -> None:
    services = _RecordingConfigurator()
    _build_firewall_context(
        cast("ServiceConfigurator", cast("object", services)),
        SecurityConfig(authenticator_factories=(OidcLoginFactory(),)),
        "api",
        FirewallConfig(
            authenticators=(
                OidcLoginConfig(
                    issuer="https://issuer.example",
                    client_id="shop",
                    client_secret="secret",
                ),
            ),
        ),
        {},
    )

    assert services.definitions[-1].arguments["listeners"] == (
        firewall_manager_listener_name("api"),
        firewall_access_listener_name("api"),
        "api#oidc_token_refresh_listener",
    )


def _http_basic_config() -> FirewallConfig:
    """A stateless firewall over the ungated http-basic authenticator."""
    from xtr_security.bundle import HttpBasicConfig

    return FirewallConfig(
        pattern=r"^/api",
        authenticators=(HttpBasicConfig(),),
    )


def test_a_stateful_firewall_parks_its_context_listener_ahead_of_the_manager() -> None:
    services = _RecordingConfigurator()
    firewall = FirewallConfig(
        pattern=r"^/api",
        stateless=False,
        authenticators=(_http_basic_config().authenticators[0],),
    )

    _build_firewall_context(
        cast("ServiceConfigurator", cast("object", services)),
        SecurityConfig(),
        "main",
        firewall,
        {},
    )

    assert services.definitions[-1].arguments["listeners"] == (
        "main#context_listener",
        firewall_manager_listener_name("main"),
        firewall_access_listener_name("main"),
    )
    assert FirewallListenerInterface in services.aliases


def test_a_stateless_firewall_registers_no_context_listener() -> None:
    services = _RecordingConfigurator()

    _build_firewall_context(
        cast("ServiceConfigurator", cast("object", services)),
        SecurityConfig(),
        "main",
        _http_basic_config(),
        {},
    )

    assert "main#context_listener" not in services.by_qualifier
    assert services.definitions[-1].arguments["listeners"] == (
        firewall_manager_listener_name("main"),
        firewall_access_listener_name("main"),
    )


def test_a_stateful_firewall_registers_its_session_strategy_subscriber() -> None:
    from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG

    services = _RecordingConfigurator()
    firewall = FirewallConfig(
        pattern=r"^/api",
        stateless=False,
        session_strategy="invalidate",
        authenticators=(_http_basic_config().authenticators[0],),
    )

    _build_firewall_context(
        cast("ServiceConfigurator", cast("object", services)),
        SecurityConfig(),
        "main",
        firewall,
        {},
    )

    assert "main#session_authentication_strategy" in services.by_qualifier
    assert SUBSCRIBER_TAG in services.tags


def test_a_configured_logout_parks_its_listener_on_the_contexts_slot() -> None:
    from xtr_security.bundle import LogoutConfig

    services = _RecordingConfigurator()
    firewall = FirewallConfig(
        pattern=r"^/api",
        logout=LogoutConfig(path="/sign-out", target_path="/bye"),
        authenticators=(_http_basic_config().authenticators[0],),
    )

    _build_firewall_context(
        cast("ServiceConfigurator", cast("object", services)),
        SecurityConfig(),
        "main",
        firewall,
        {},
    )

    assert "main#logout_listener" in services.by_qualifier
    factory = cast("Callable[..., object]", services.set_targets[-1])
    assert (
        factory.__annotations__["logout"]
        == Annotated[LogoutListener, Target("main#logout_listener")]
    )


def test_a_logout_asking_for_a_csrf_check_fails_the_build() -> None:
    from xtr_security.bundle import LogoutConfig

    services = _RecordingConfigurator()
    firewall = FirewallConfig(
        pattern=r"^/api",
        logout=LogoutConfig(enable_csrf=True),
        authenticators=(_http_basic_config().authenticators[0],),
    )

    with pytest.raises(InvalidConfigurationError, match="enable_csrf"):
        _build_firewall_context(
            cast("ServiceConfigurator", cast("object", services)),
            SecurityConfig(),
            "main",
            firewall,
            {},
        )


def test_the_logout_url_generator_registers_every_configured_firewall() -> None:
    from xtr_security_http import LogoutUrlGenerator

    from xtr_security.bundle._logout_wiring import register_logout_url_generator

    services = _RecordingConfigurator()

    register_logout_url_generator(
        cast("ServiceConfigurator", cast("object", services)),
        {"main": ("/sign-out", "main"), "api": ("/logout", None)},
    )

    generator = cast("Callable[..., object]", services.set_targets[-1])
    assert generator.__annotations__["return"] is LogoutUrlGenerator


def test_a_backchannel_logout_on_a_stateless_firewall_fails_the_build() -> None:
    services = _RecordingConfigurator()
    firewall = FirewallConfig(
        pattern=r"^/api",
        authenticators=(
            OidcLoginConfig(
                issuer="https://issuer.example",
                client_id="shop",
                client_secret="secret",
                backchannel_logout=OidcBackChannelLogoutConfig(),
            ),
        ),
    )

    with pytest.raises(InvalidConfigurationError, match="stateless=False"):
        _build_firewall_context(
            cast("ServiceConfigurator", cast("object", services)),
            SecurityConfig(authenticator_factories=(OidcLoginFactory(),)),
            "api",
            firewall,
            {},
        )
