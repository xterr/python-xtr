"""The firewall listener chains are sorted by priority, and by the neighbours they declare."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_dependency_injection import ContainerBuilder, Origin
from xtr_dependency_injection.builder.service_configurator import BuildState
from xtr_security_http.decorator.firewall_listener_order import FirewallListenerOrder
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface

from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.security_config import SecurityConfig
from xtr_security.bundle.sort_firewall_listeners_pass import SortFirewallListenersPass
from xtr_security.exception import InvalidConfigurationError
from xtr_security.firewall_config import FirewallConfig

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface


class ChainListener(AbstractListener):
    """A chain member whose hooks do nothing: the priority is what varies per fake."""

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        return None


@final
class EarlyListener(ChainListener):
    @staticmethod
    @override
    def get_priority() -> int:
        return 256


@final
class LateListener(ChainListener):
    pass


@final
class CleanupListener(ChainListener):
    @staticmethod
    @override
    def get_priority() -> int:
        return -255


@final
class PlainListener:
    """A chain member that is no firewall listener at all: it runs at the default priority."""


@final
class SecondListener(ChainListener):
    pass


@FirewallListenerOrder(before=SecondListener)
@final
class AheadOfSecondListener(ChainListener):
    pass


@FirewallListenerOrder(before=EarlyListener)
@final
class OverreachingListener(ChainListener):
    pass


@final
class StubPriorityListener(  # pyright: ignore[reportGeneralTypeIssues]  # ty: ignore[abstract-method-in-final-class]  -- deliberately incomplete: it inherits the interface's member unimplemented
    FirewallListenerInterface,
):
    """A listener inheriting the interface's member without overriding it."""

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        return None


def _builder(*firewalls: str) -> ContainerBuilder:
    config = SecurityConfig(firewalls={name: FirewallConfig(security=False) for name in firewalls})
    state = BuildState(env="test", debug=False, bundles=("security",), configs={"security": config})
    state.phase = "process"
    return ContainerBuilder(state, Origin("bundle", "security"))


def _chain(builder: ContainerBuilder, firewall: str, listeners: object) -> None:
    """Park ``listeners`` as the ``firewall``'s chain, the way the wiring gathers one."""
    _ = builder.register(FirewallContext, qualifier=firewall).set_argument("listeners", listeners)


def _listener(builder: ContainerBuilder, listener_class: type, qualifier: str) -> None:
    """Register a listener and alias it under the interface, as a chain names it."""
    _ = builder.register(listener_class, qualifier=qualifier)
    builder.set_alias(
        FirewallListenerInterface,
        listener_class,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )


def _sorted_chain(builder: ContainerBuilder, firewall: str) -> object:
    return builder.get_definition(FirewallContext, firewall).get_arguments()["listeners"]


def test_listeners_run_by_priority_highest_first() -> None:
    builder = _builder("api")
    for listener_class, qualifier in (
        (LateListener, "late"),
        (EarlyListener, "early"),
        (CleanupListener, "cleanup"),
    ):
        _listener(builder, listener_class, qualifier)
    _chain(builder, "api", ("late", "early", "cleanup"))

    SortFirewallListenersPass().process(builder)

    assert _sorted_chain(builder, "api") == ("early", "late", "cleanup")


def test_listeners_sharing_a_priority_keep_their_gathering_order() -> None:
    builder = _builder("api")
    for qualifier in ("first", "second", "third"):
        _listener(builder, LateListener, qualifier)
    _chain(builder, "api", ("first", "second", "third"))

    SortFirewallListenersPass().process(builder)

    assert _sorted_chain(builder, "api") == ("first", "second", "third")


def test_a_chain_member_that_is_no_listener_runs_at_the_default_priority() -> None:
    builder = _builder("api")
    _listener(builder, PlainListener, "plain")
    _listener(builder, CleanupListener, "cleanup")
    _chain(builder, "api", ("plain", "cleanup"))

    SortFirewallListenersPass().process(builder)

    assert _sorted_chain(builder, "api") == ("plain", "cleanup")


def test_a_declared_neighbour_reorders_within_a_shared_priority() -> None:
    builder = _builder("api")
    _listener(builder, SecondListener, "second")
    _listener(builder, AheadOfSecondListener, "ahead")
    _chain(builder, "api", ("second", "ahead"))

    SortFirewallListenersPass().process(builder)

    assert _sorted_chain(builder, "api") == ("ahead", "second")


def test_a_constraint_that_would_cross_a_priority_fails_the_build() -> None:
    builder = _builder("api")
    _listener(builder, EarlyListener, "early")
    _listener(builder, OverreachingListener, "overreaching")
    _chain(builder, "api", ("early", "overreaching"))

    with pytest.raises(InvalidConfigurationError, match='firewall "api"'):
        SortFirewallListenersPass().process(builder)


def test_a_chain_naming_an_unknown_qualifier_fails_the_build() -> None:
    builder = _builder("api")
    _chain(builder, "api", ("nowhere",))

    with pytest.raises(InvalidConfigurationError, match="nowhere"):
        SortFirewallListenersPass().process(builder)


def test_a_listener_inheriting_the_interface_member_without_overriding_it_fails() -> None:
    builder = _builder("api")
    _listener(builder, StubPriorityListener, "stub")
    _chain(builder, "api", ("stub",))

    with pytest.raises(InvalidConfigurationError, match="StubPriorityListener"):
        SortFirewallListenersPass().process(builder)


def test_a_firewall_without_a_chain_is_left_untouched() -> None:
    builder = _builder("api")
    _ = builder.register(FirewallContext, qualifier="api")

    SortFirewallListenersPass().process(builder)

    assert builder.get_definition(FirewallContext, "api").get_arguments() == {}


def test_a_firewall_without_a_context_definition_is_skipped() -> None:
    builder = _builder("api")

    SortFirewallListenersPass().process(builder)


def test_a_configuration_without_firewalls_builds_as_before() -> None:
    SortFirewallListenersPass().process(_builder())
