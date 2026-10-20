"""The pass placing the per-call listeners into the dispatchers' maps."""

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING, Annotated, cast, final

from xtr_dependency_injection import Target
from xtr_event_dispatcher.bundle import ListenerMap
from xtr_event_dispatcher_contracts import event_name_of
from xtr_http_kernel import RequestEvent, ResponseEvent
from xtr_security_http import CheckPassportEvent, ContextListener, LogoutEvent
from xtr_security_http.session.session_authentication_strategy import (
    SessionAuthenticationStrategy,
)

from xtr_security.bundle import FormLoginConfig, SecurityConfig
from xtr_security.bundle._csrf_listeners import (
    PerCallListener,
    check_the_passport_token,
    clear_csrf_tokens_on_logout,
)
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.register_per_call_listeners_pass import RegisterPerCallListenersPass
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

    def __init__(self, config: SecurityConfig, listeners: Map) -> None:
        self._config = config
        self._listeners = listeners
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
    by_event = cast(
        "Mapping[str, tuple[tuple[int, ListenerReference], ...]]",
        {event_name_of(event): tuple(entries)},
    )
    return cast("Map", cast("object", ListenerMap(by_event)))


def _function_of(entry: object) -> Callable[..., object]:
    """Return the function the per-call reference ``entry`` holds."""
    return cast("PerCallListener", entry)._function


def test_a_form_login_asking_for_a_token_places_the_check_ahead_of_its_priority_group() -> None:
    resolve_user, provider = object(), object()
    listeners = _map_of(
        CheckPassportEvent,
        (2048, provider),
        (512, resolve_user),
        (128, object()),
    )
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(FormLoginConfig(login_path="/login", enable_csrf=True),),
            )
        }
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    placed = cast(
        "Map", builder.definitions[firewall_dispatcher_name("main")].set_arguments["listeners"]
    )
    entries = placed.by_event[event_name_of(CheckPassportEvent)]
    assert [priority for priority, _ in entries] == [2048, 512, 512, 128]
    assert entries[1][1].__class__.__name__ == "PerCallListener"
    assert _function_of(entries[1][1]) is check_the_passport_token
    assert entries[2][1] is resolve_user


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


def test_a_firewall_asking_nowhere_leaves_its_dispatchers_map_alone() -> None:
    listeners = _map_with((0, object()))
    config = SecurityConfig(
        firewalls={"main": FirewallConfig(authenticators=(FormLoginConfig(login_path="/login"),))}
    )
    builder = _Builder(config, listeners)

    RegisterPerCallListenersPass().process(cast("ContainerBuilder", cast("object", builder)))

    assert builder.definitions[firewall_dispatcher_name("main")].set_arguments == {}


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
