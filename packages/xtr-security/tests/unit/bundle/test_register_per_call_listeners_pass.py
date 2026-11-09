"""The pass placing the per-call listeners into the dispatchers' maps."""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, Annotated, cast, final

import pytest
from xtr_dependency_injection import Target
from xtr_event_dispatcher.bundle import ListenerMap
from xtr_event_dispatcher_contracts import event_name_of
from xtr_http_kernel import RequestEvent, ResponseEvent
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    CheckPassportEvent,
    ContextListener,
    LoginFailureEvent,
    LoginSuccessEvent,
    LogoutEvent,
    SignatureRememberMeHandler,
    TokenDeauthenticatedEvent,
)
from xtr_security_http.session.session_authentication_strategy import (
    SessionAuthenticationStrategy,
)

from xtr_security.bundle import (
    FormLoginConfig,
    InMemoryUserProviderConfig,
    RememberMeConfig,
    SecurityConfig,
)
from xtr_security.bundle._csrf_listeners import (
    PerCallListener,
    check_the_passport_token,
    clear_csrf_tokens_on_logout,
)
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.register_per_call_listeners_pass import RegisterPerCallListenersPass
from xtr_security.exception import InvalidConfigurationError
from xtr_security.firewall_config import FirewallConfig
from xtr_security.logout_config import LogoutConfig

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from xtr_event_dispatcher.bundle import ListenerMap as Map
    from xtr_event_dispatcher.bundle._listener_reference import ListenerReference


@final
class _Definition:
    """A stand-in definition recording the argument the pass sets."""

    def __init__(self, listeners: Map) -> None:
        self._listeners = listeners
        self.set_arguments: dict[str, object] = {}

    def get_arguments(self) -> dict[str, object]:
        """Return the arguments the dispatcher's factory is registered with."""
        return {"listeners": self._listeners}

    def set_argument(self, name: str, value: object, /) -> _Definition:
        self.set_arguments[name] = value
        return self


@final
class _Builder:
    """A stand-in builder holding one dispatcher definition per firewall."""

    def __init__(
        self,
        config: SecurityConfig,
        listeners: Map,
        services: frozenset[type] | None = None,
    ) -> None:
        self._config = config
        self._listeners = listeners
        self._services = services if services is not None else frozenset[type]()
        self.definitions: dict[str | None, _Definition] = {
            firewall_dispatcher_name(name): _Definition(listeners)
            for name in config.firewalls
            if config.firewalls[name].security
        }
        # The main dispatcher, keyed the way the container holds it: no qualifier.
        self.definitions[None] = _Definition(listeners)

    def get_extension_config(self, bundle: type, /) -> SecurityConfig:
        """Return the configuration the firewalls come from."""
        del bundle
        return self._config

    def has_definition(self, service: type, qualifier: Hashable | None, /) -> bool:
        """Tell whether the dispatcher ``qualifier`` names is registered."""
        del service
        return qualifier in self.definitions

    def has(self, service: type, /, qualifier: Hashable | None = None) -> bool:
        """Tell whether the application registered ``service``."""
        del qualifier
        return service in self._services

    def get_definition(self, service: type, qualifier: Hashable | None, /) -> _Definition:
        """Return the dispatcher ``qualifier`` names."""
        del service
        return self.definitions[cast("str", qualifier)]


def _map_with(*entries: tuple[int, object]) -> Map:
    """Return a listener map carrying one event's entries, in the order given."""
    by_event = cast(
        "Mapping[str, tuple[tuple[int, ListenerReference], ...]]",
        {"an event": tuple(entries)},
    )
    return cast("Map", cast("object", ListenerMap(by_event)))


def _map_of(event: type, *entries: tuple[int, object]) -> Map:
    """Return a listener map carrying ``event``'s entries, in the order given."""
    return _map_of_events({event: entries})


def _map_of_events(events: Mapping[type, tuple[tuple[int, object], ...]]) -> Map:
    """Return a listener map carrying each event's entries, in the order given."""
    by_event = cast(
        "Mapping[str, tuple[tuple[int, ListenerReference], ...]]",
        {event_name_of(event): tuple(entries) for event, entries in events.items()},
    )
    return cast("Map", cast("object", ListenerMap(by_event)))


def _function_of(entry: object) -> Callable[..., object]:
    """Return the function the per-call reference ``entry`` holds."""
    return cast("PerCallListener", entry)._function


def _name_of(entry: object) -> str:
    """Return the name of the function the per-call reference ``entry`` holds."""
    return cast("str", getattr(_function_of(entry), "__name__", ""))


def _placed(builder: _Builder, event: type, firewall: str = "main") -> list[tuple[int, object]]:
    """Return the entries the pass left on ``firewall``'s dispatcher for ``event``."""
    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name(firewall)].set_arguments["listeners"]
    )
    return list(placed.by_event[event_name_of(event)])


_PROVIDERS = {"users": InMemoryUserProviderConfig(users={})}


def test_a_form_login_asking_for_a_token_places_the_check_ahead_of_its_priority_group() -> None:
    throttle, resolve_user, verify = object(), object(), object()
    listeners = _map_of(
        CheckPassportEvent,
        (2080, throttle),
        (512, resolve_user),
        (128, verify),
    )
    config = SecurityConfig(
        providers=_PROVIDERS,
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                provider="users",
                authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),),
            )
        },
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    entries = _placed(builder, CheckPassportEvent)
    assert [priority for priority, _ in entries] == [2080, 2048, 512, 512, 256, 128]
    assert entries[0][1] is throttle
    assert _name_of(entries[1][1]) == "load_the_user"
    assert entries[2][1].__class__.__name__ == "PerCallListener"
    assert _function_of(entries[2][1]) is check_the_passport_token
    assert entries[3][1] is resolve_user
    assert _name_of(entries[4][1]) == "check_the_account_before_credentials"
    assert entries[5][1] is verify


def test_a_logout_clearing_its_tokens_places_the_clearing_behind_its_priority_group() -> None:
    site_data = object()
    listeners = _map_of(LogoutEvent, (0, site_data), (-255, object()))
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login"),),
                logout=LogoutConfig(clear_csrf_tokens=True),
            )
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name("main")].set_arguments["listeners"]
    )
    entries = placed.by_event[event_name_of(LogoutEvent)]
    assert [priority for priority, _ in entries] == [0, 0, -255]
    assert entries[0][1] is site_data
    assert _function_of(entries[1][1]) is clear_csrf_tokens_on_logout


def test_a_firewall_asking_for_nothing_else_gains_only_the_account_checks() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name("main")].set_arguments["listeners"]
    )
    assert set(placed.by_event) == {
        "an event",
        event_name_of(CheckPassportEvent),
        event_name_of(AuthenticationSuccessEvent),
    }
    assert [_name_of(entry) for _, entry in placed.by_event[event_name_of(CheckPassportEvent)]] == [
        "check_the_account_before_credentials"
    ]


def test_the_user_load_runs_first_among_the_listeners_at_its_priority() -> None:
    throttle, shared = object(), object()
    listeners = _map_of(CheckPassportEvent, (2080, throttle), (2048, shared))
    config = SecurityConfig(
        providers=_PROVIDERS,
        firewalls={
            "main": FirewallConfig(
                provider="users", authenticators=(FormLoginConfig(login_path="/login"),)
            )
        },
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    entries = _placed(builder, CheckPassportEvent)
    assert [priority for priority, _ in entries] == [2080, 2048, 2048, 256]
    assert entries[0][1] is throttle
    load = _function_of(entries[1][1])
    assert getattr(load, "__name__", "") == "load_the_user"
    assert load.__annotations__["provider"] == Annotated[UserProviderInterface, Target("users")]
    assert entries[2][1] is shared


def test_a_firewall_naming_no_provider_gains_no_user_load() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    assert "load_the_user" not in [
        _name_of(entry) for _, entry in _placed(builder, CheckPassportEvent)
    ]


def test_the_account_checks_run_ahead_of_the_shared_listeners_at_their_priority() -> None:
    shared_before, shared_after = object(), object()
    listeners = _map_of_events(
        {
            CheckPassportEvent: ((256, shared_before),),
            AuthenticationSuccessEvent: ((256, shared_after),),
        }
    )
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    before = _placed(builder, CheckPassportEvent)
    assert _name_of(before[0][1]) == "check_the_account_before_credentials"
    assert before[1][1] is shared_before
    after = _placed(builder, AuthenticationSuccessEvent)
    assert [priority for priority, _ in after] == [256, 256]
    assert _name_of(after[0][1]) == "check_the_account_after_login"
    assert after[1][1] is shared_after


def test_a_remembered_login_is_set_after_the_conditions_and_cleared_on_every_ending() -> None:
    conditions = object()
    listeners = _map_of(LoginSuccessEvent, (-32, conditions))
    config = SecurityConfig(
        providers=_PROVIDERS,
        firewalls={
            "main": FirewallConfig(
                provider="users",
                authenticators=(FormLoginConfig(login_path="/login"), RememberMeConfig()),
            )
        },
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    success = _placed(builder, LoginSuccessEvent)
    assert [priority for priority, _ in success] == [-32, -64]
    assert success[0][1] is conditions
    remember = _function_of(success[1][1])
    assert getattr(remember, "__name__", "") == "remember_the_login"
    assert (
        remember.__annotations__["handler"]
        == Annotated[SignatureRememberMeHandler, Target("main#remember_me_handler")]
    )
    for ending in (LoginFailureEvent, LogoutEvent, TokenDeauthenticatedEvent):
        assert [_name_of(entry) for _, entry in _placed(builder, ending)] == ["forget_the_login"]


def test_on_logout_the_cookie_is_cleared_before_the_forgery_tokens() -> None:
    session_logout, last = object(), object()
    listeners = _map_of(LogoutEvent, (0, session_logout), (-255, last))
    config = SecurityConfig(
        providers=_PROVIDERS,
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                provider="users",
                authenticators=(FormLoginConfig(login_path="/login"), RememberMeConfig()),
                logout=LogoutConfig(clear_csrf_tokens=True),
            )
        },
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    entries = _placed(builder, LogoutEvent)
    assert [priority for priority, _ in entries] == [0, 0, 0, -255]
    assert entries[0][1] is session_logout
    assert _name_of(entries[1][1]) == "forget_the_login"
    assert _function_of(entries[2][1]) is clear_csrf_tokens_on_logout
    assert entries[3][1] is last


def test_a_firewall_without_remember_me_gains_no_cookie_listener() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name("main")].set_arguments["listeners"]
    )
    assert event_name_of(LoginFailureEvent) not in placed.by_event
    assert event_name_of(TokenDeauthenticatedEvent) not in placed.by_event


def test_a_user_checker_no_service_provides_fails_the_build() -> None:
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                user_checker=_AppChecker,
                authenticators=(FormLoginConfig(login_path="/login"),),
            )
        }
    )
    builder = _Builder(config, _map_with((0, object())))

    with pytest.raises(InvalidConfigurationError, match="_AppChecker, which no service provides"):
        RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))


def test_a_registered_user_checker_is_what_the_account_checks_inject() -> None:
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                user_checker=_AppChecker,
                authenticators=(FormLoginConfig(login_path="/login"),),
            )
        }
    )
    builder = _Builder(config, _map_with((0, object())), frozenset({_AppChecker}))

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    check = _function_of(_placed(builder, CheckPassportEvent)[0][1])
    assert "checker" in check.__annotations__


@final
class _AppChecker:
    """A checker class the application named on the firewall."""

    __slots__ = ()


def test_an_open_firewall_has_no_dispatcher_to_place_listeners_in() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={
            "open": FirewallConfig(security=False, authenticators=()),
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),),
            ),
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    assert firewall_dispatcher_name("open") not in builder.definitions
    assert builder.definitions[firewall_dispatcher_name("main")].set_arguments != {}


def test_a_stateful_firewall_gets_the_session_strategy_listener() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login"),),
            )
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    from xtr_security_http.event.login_success_event import LoginSuccessEvent

    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name("main")].set_arguments["listeners"]
    )
    entries = placed.by_event[event_name_of(LoginSuccessEvent)]
    strategy_listener = _function_of(entries[0][1])
    assert getattr(strategy_listener, "__name__", "") == "apply_the_session_strategy"
    assert (
        strategy_listener.__annotations__["strategy"]
        == Annotated[SessionAuthenticationStrategy, Target("main#session_authentication_strategy")]
    )


def test_a_stateful_firewalls_context_write_back_joins_the_main_dispatchers_response() -> None:
    ahead, behind = object(), object()
    listeners = _map_of(ResponseEvent, (0, ahead), (-1000, behind))
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login"),),
            )
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast("Map", builder.definitions[None].set_arguments["listeners"])
    entries = placed.by_event[event_name_of(ResponseEvent)]
    assert [priority for priority, _ in entries] == [0, 0, -1000]
    assert entries[0][1] is ahead
    write_back = _function_of(entries[1][1])
    assert getattr(write_back, "__name__", "") == "store_the_token"
    assert (
        write_back.__annotations__["context_listener"]
        == Annotated[ContextListener, Target("main#context_listener")]
    )
    assert entries[2][1] is behind


def test_no_stateful_firewall_leaves_the_main_dispatcher_alone() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    assert builder.definitions[None].set_arguments == {}


def test_a_firewall_with_a_logout_gains_the_current_firewall_namer_after_the_firewall() -> None:
    router, firewall_step = object(), object()
    listeners = _map_of(RequestEvent, (32, router), (8, firewall_step), (0, object()))
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login"),),
                logout=LogoutConfig(),
            )
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast("Map", builder.definitions[None].set_arguments["listeners"])
    entries = placed.by_event[event_name_of(RequestEvent)]
    assert [priority for priority, _ in entries] == [32, 8, 4, 0]
    assert entries[0][1] is router
    assert entries[1][1] is firewall_step
    namer = _function_of(entries[2][1])
    assert getattr(namer, "__name__", "") == "name_the_matched_firewall"


if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder
