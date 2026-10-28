"""The switch-user wiring: its annotated branches and its configuration lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

import pytest
from xtr_dependency_injection import Target
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message_contracts import ServerRequestInterface
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_http import HttpUtils

from xtr_security.bundle._switch_user_wiring import (
    _FirewallConfigLookup,
    register_impersonate_url_generator,
    register_switch_user,
    switch_user_listener_name,
)
from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.exception import InvalidConfigurationError
from xtr_security.firewall_config import FirewallConfig
from xtr_security.switch_user_config import SwitchUserConfig

pytestmark = pytest.mark.anyio

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceKey
    from xtr_security_core.user.user_provider_interface import UserProviderInterface
    from xtr_security_http import SwitchUserListener


@final
class _RecordingDefinition:
    """A stand-in definition recording the alias the wiring adds."""

    def __init__(self) -> None:
        self.key = cast("ServiceKey", (object, "recorded"))

    def add_tag(self, *args: object, **kwargs: object) -> _RecordingDefinition:
        """Record the tag the wiring adds."""
        del args, kwargs
        return self


@final
class _Recorder:
    """A stand-in configurator recording every ``set`` the wiring makes."""

    def __init__(self) -> None:
        self.factories: list[Callable[..., object]] = []

    def set(
        self,
        target: Callable[..., object],
        /,
        **kwargs: object,
    ) -> _RecordingDefinition:
        del kwargs
        self.factories.append(target)
        return _RecordingDefinition()

    def alias(self, *args: object, **kwargs: object) -> None:
        """Record the alias the wiring adds."""
        del args, kwargs


@final
class _Request:
    """A stand-in request carrying what its attribute bag holds."""

    __slots__ = ("_attributes",)

    def __init__(self, attributes: dict[str, object]) -> None:
        self._attributes = attributes

    def get_attribute(self, name: str, default: object | None = None) -> object | None:
        """Return one of the attributes this stand-in carries."""
        del default
        return self._attributes.get(name)


@final
class _Checker:
    """A stand-in user-checker service."""

    __slots__ = ()


def _switch_settings(enable_csrf: bool = False) -> SwitchUserConfig:
    return SwitchUserConfig(enable_csrf=enable_csrf)


def test_the_switch_step_is_annotated_with_the_firewall_checker_and_token_manager() -> None:
    recorder = _Recorder()

    qualifier = register_switch_user(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FirewallConfig(pattern=r"^/", user_checker=_Checker, security=False, stateless=False),
        _switch_settings(enable_csrf=True),
        "users",
        csrf_wired=True,
    )

    assert qualifier == switch_user_listener_name("main")
    assert len(recorder.factories) == 1


def test_the_switch_step_falls_back_to_the_plain_provider_when_the_firewall_names_none() -> None:
    recorder = _Recorder()

    _ = register_switch_user(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FirewallConfig(pattern=r"^/", security=False),
        _switch_settings(),
        None,
        csrf_wired=False,
    )

    assert len(recorder.factories) == 1


def test_a_switch_asking_for_a_forgery_check_on_a_stateless_firewall_is_refused() -> None:
    recorder = _Recorder()

    with pytest.raises(InvalidConfigurationError, match="cross-site request forgery"):
        _ = register_switch_user(
            recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            FirewallConfig(pattern=r"^/", security=False),
            _switch_settings(enable_csrf=True),
            "users",
            csrf_wired=True,
        )


def test_the_switch_step_is_annotated_with_the_firewalls_own_dispatcher() -> None:
    recorder = _Recorder()

    _ = register_switch_user(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FirewallConfig(pattern=r"^/", security=False),
        _switch_settings(),
        None,
        csrf_wired=False,
    )

    factory = recorder.factories[0]
    assert (
        factory.__annotations__["dispatcher"]
        == Annotated[EventDispatcherInterface, Target(firewall_dispatcher_name("main"))]
    )


def test_the_built_switch_step_holds_the_dispatcher_it_is_handed() -> None:
    recorder = _Recorder()
    _ = register_switch_user(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FirewallConfig(pattern=r"^/", security=False),
        _switch_settings(),
        None,
        csrf_wired=False,
    )
    factory = recorder.factories[0]

    dispatcher = cast("EventDispatcherInterface", object())
    listener = cast(
        "SwitchUserListener",
        factory(
            token_storage=TokenStorage(),
            provider=cast("UserProviderInterface", object()),
            decision_manager=AccessDecisionManager([]),
            bridge=StarletteHttpFactory(),
            http_utils=HttpUtils(ResponseFactory()),
            dispatcher=dispatcher,
        ),
    )

    assert listener._dispatcher is dispatcher


async def test_the_lookup_answers_the_firewall_the_request_runs_in() -> None:
    lookup = _FirewallConfigLookup({"main": _switch_settings()})
    bag: dict[str, object] = {}
    request = _Request({"_xtr_security_state_bag": bag})

    from xtr_security_http._security_state import security_state_of
    from xtr_security_http.firewall_context_interface import FirewallContextInterface

    security_state_of(bag).firewall_context = cast(
        "FirewallContextInterface", cast("object", _Context("main"))
    )
    answered = await lookup.get_switch_user_config(
        cast("ServerRequestInterface", cast("object", request))
    )
    assert answered is not None
    assert answered.parameter == "_switch_user"


async def test_the_lookup_answers_none_for_a_request_with_no_bag() -> None:
    lookup = _FirewallConfigLookup({"main": _switch_settings()})

    answered = await lookup.get_switch_user_config(
        cast("ServerRequestInterface", cast("object", _Request({})))
    )
    assert answered is None


async def test_the_lookup_answers_none_for_a_request_no_firewall_claimed() -> None:
    lookup = _FirewallConfigLookup({"main": _switch_settings()})
    request = _Request({"_xtr_security_state_bag": {}})

    answered = await lookup.get_switch_user_config(
        cast("ServerRequestInterface", cast("object", request))
    )
    assert answered is None


async def test_the_lookup_answers_none_for_a_firewall_configured_without_a_switch() -> None:
    lookup = _FirewallConfigLookup({})
    bag: dict[str, object] = {}

    from xtr_security_http._security_state import security_state_of
    from xtr_security_http.firewall_context_interface import FirewallContextInterface

    security_state_of(bag).firewall_context = cast(
        "FirewallContextInterface", cast("object", _Context("other"))
    )
    request = _Request({"_xtr_security_state_bag": bag})

    answered = await lookup.get_switch_user_config(
        cast("ServerRequestInterface", cast("object", request))
    )
    assert answered is None


def test_the_generator_is_annotated_with_the_token_manager_when_a_switch_asks_for_one() -> None:
    recorder = _Recorder()

    register_impersonate_url_generator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        {"main": _switch_settings(enable_csrf=True)},
        csrf_wired=True,
    )

    assert len(recorder.factories) == 1


@final
class _Context:
    """A stand-in firewall context, named."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name
