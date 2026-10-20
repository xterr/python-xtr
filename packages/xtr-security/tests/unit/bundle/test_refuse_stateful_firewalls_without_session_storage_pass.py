"""A stateful firewall with no session storage is refused, naming the service."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import ContainerBuilder, Origin
from xtr_dependency_injection.builder.service_configurator import BuildState
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall_listener_interface import (
    FirewallListenerInterface,
)

from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.bundle.refuse_stateful_firewalls_without_session_storage_pass import (
    RefuseStatefulFirewallsWithoutSessionStoragePass,
)
from xtr_security.bundle.security_config import SecurityConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.firewall_config import FirewallConfig

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface

import pytest


@final
class _ChainListener(AbstractListener):
    """A chain member whose hooks do nothing."""

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        return None


def _builder(stateless: bool) -> ContainerBuilder:
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=stateless,
                authenticators=(object(),),
            )
        }
    )
    state = BuildState(env="test", debug=False, bundles=("security",), configs={"security": config})
    state.phase = "process"
    builder = ContainerBuilder(state, Origin("bundle", "security"))
    _ = builder.register(FirewallContext, qualifier="main")
    return builder


def _register_context_listener(builder: ContainerBuilder) -> None:
    """Register a listener and alias it under the chain's interface, as the wiring does."""
    _ = builder.register(_ChainListener, qualifier="main#context_listener")
    builder.set_alias(
        FirewallListenerInterface,
        _ChainListener,
        alias_qualifier="main#context_listener",
        target_qualifier="main#context_listener",
    )


def test_a_stateful_firewall_without_its_listener_is_refused() -> None:
    builder = _builder(stateless=False)

    with pytest.raises(InvalidConfigurationError, match="SessionStorageInterface"):
        RefuseStatefulFirewallsWithoutSessionStoragePass().process(builder)


def test_a_stateful_firewall_with_its_listener_passes() -> None:
    builder = _builder(stateless=False)
    _register_context_listener(builder)

    RefuseStatefulFirewallsWithoutSessionStoragePass().process(builder)


def test_a_stateless_firewall_is_left_alone() -> None:
    builder = _builder(stateless=True)

    RefuseStatefulFirewallsWithoutSessionStoragePass().process(builder)


def test_a_stateful_firewall_without_a_context_is_left_alone() -> None:
    """A firewall the wiring never gathered a context for is not this pass's to refuse."""
    config = SecurityConfig(
        firewalls={
            "main": FirewallConfig(
                stateless=False,
                authenticators=(object(),),
            )
        }
    )
    state = BuildState(env="test", debug=False, bundles=("security",), configs={"security": config})
    state.phase = "process"
    builder = ContainerBuilder(state, Origin("bundle", "security"))

    RefuseStatefulFirewallsWithoutSessionStoragePass().process(builder)


def test_an_open_firewall_is_left_alone() -> None:
    config = SecurityConfig(firewalls={"open": FirewallConfig(security=False)})
    state = BuildState(env="test", debug=False, bundles=("security",), configs={"security": config})
    state.phase = "process"
    builder = ContainerBuilder(state, Origin("bundle", "security"))

    RefuseStatefulFirewallsWithoutSessionStoragePass().process(builder)
