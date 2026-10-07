"""The security bundle honours the zero-config contract and fails a bad build."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_dependency_injection import Kernel, unit_of_work
from xtr_dependency_injection.testing import assert_zero_config, boot_for_test
from xtr_security_core import AccessDecisionManagerInterface, TokenStorageInterface
from xtr_security_http.firewall_map_interface import FirewallMapInterface

from xtr_security.bundle import OidcTokenHandlerFactory, SecurityBundle, SecurityConfig

if TYPE_CHECKING:
    from xtr_security.access_token.oidc_token_handler_factory import _AsyncCloseable

pytestmark = pytest.mark.anyio


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(SecurityBundle)


async def test_the_core_services_are_registered_unconfigured() -> None:
    kernel = Kernel(
        "tests.fixtures.security_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
    )
    async with await boot_for_test(kernel) as booted:
        assert booted.container.has(AccessDecisionManagerInterface)
        assert booted.container.has(TokenStorageInterface)


async def test_the_firewall_map_is_empty_when_no_firewall_is_configured() -> None:
    kernel = Kernel(
        "tests.fixtures.probe_app",
        env="test",
        bundles={SecurityBundle: {"all": True}},
        concurrent_scoped_access=True,
    )
    async with await boot_for_test(kernel) as booted, unit_of_work(booted.container) as unit:
        firewall_map = await unit.get(FirewallMapInterface)

    assert firewall_map.names() == ()


@final
class _RecordingCloseable:
    """A key-set provider stand-in counting how often the bundle closed it."""

    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


@final
class _FailingCloseable:
    """A key-set provider stand-in whose close raises, recording the attempt."""

    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1
        message = "client refused to close"
        raise RuntimeError(message)


def _oidc_sink(bundle: SecurityBundle) -> list[_AsyncCloseable]:
    """Return the list the bundle's bound OIDC factory records providers into."""
    bound = bundle._bind_oidc_closeables(
        SecurityConfig(token_handler_factories=(OidcTokenHandlerFactory(),)),
    )
    factory = cast("OidcTokenHandlerFactory", bound.token_handler_factories[0])
    sink = factory._closeables
    assert sink is not None
    return sink


async def test_shutdown_closes_every_collected_provider_and_empties_the_sink() -> None:
    bundle = SecurityBundle()
    sink = _oidc_sink(bundle)
    first = _RecordingCloseable()
    second = _RecordingCloseable()
    sink.extend((first, second))

    await bundle.shutdown()

    assert (first.closed, second.closed) == (1, 1)
    assert sink == []


async def test_shutdown_closes_every_provider_even_when_one_fails_and_raises_a_group() -> None:
    bundle = SecurityBundle()
    sink = _oidc_sink(bundle)
    first = _FailingCloseable()
    second = _RecordingCloseable()
    third = _FailingCloseable()
    sink.extend((first, second, third))

    with pytest.raises(ExceptionGroup) as caught:
        await bundle.shutdown()

    assert (first.closed, second.closed, third.closed) == (1, 1, 1)
    assert sink == []
    assert [type(error) for error in caught.value.exceptions] == [RuntimeError, RuntimeError]


async def test_a_second_run_closes_the_providers_it_collected_too() -> None:
    bundle = SecurityBundle()
    sink = _oidc_sink(bundle)

    first = _RecordingCloseable()
    sink.append(first)
    await bundle.shutdown()
    second = _RecordingCloseable()
    sink.append(second)
    await bundle.shutdown()

    assert (first.closed, second.closed) == (1, 1)
    assert sink == []
