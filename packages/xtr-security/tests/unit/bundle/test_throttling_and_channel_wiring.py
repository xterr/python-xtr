"""The throttling listener's refusal, and the channel rule's validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_dependency_injection import Kernel
from xtr_rate_limiter import InMemoryStorage
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http import ChannelListener

from tests.fixtures.remember_me_app.bundles import BUNDLES
from xtr_security.bundle._channel_wiring import firewall_channel_listener_name
from xtr_security.bundle._throttling_wiring import register_login_throttling
from xtr_security.bundle.access_control_configs import AccessControlConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.login_throttling_config import LoginThrottlingConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ServiceKey


@final
class _RecordingDefinition:
    """A stand-in definition recording nothing the wiring reads back."""

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


def test_the_throttling_listener_fails_naming_the_secret_when_it_is_absent() -> None:
    recorder = _Recorder()
    register_login_throttling(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginThrottlingConfig(),
    )

    with pytest.raises(InvalidConfigurationError, match='"secret"'):
        _ = recorder.factories[0](InMemoryStorage(), clock=None, firewall_dispatcher=None)


def test_the_throttling_listener_builds_its_two_limiters_when_the_secret_is_supplied() -> None:
    from xtr_security_http import LoginThrottlingListener

    recorder = _Recorder()
    register_login_throttling(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginThrottlingConfig(secret="counting", global_limit=3),
    )

    listener = recorder.factories[0](InMemoryStorage(), clock=None, firewall_dispatcher=None)
    assert isinstance(listener, LoginThrottlingListener)


def test_the_throttling_listener_asks_for_no_lock_factory_without_the_lock_bundle() -> None:
    recorder = _Recorder()
    register_login_throttling(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginThrottlingConfig(secret="counting"),
    )

    assert "lock_factory" not in recorder.factories[0].__annotations__


def test_the_throttling_listener_locks_through_the_lock_bundle_when_it_is_active() -> None:
    from xtr_lock import InMemoryStore, LockFactory
    from xtr_security_http import LoginThrottlingListener

    recorder = _Recorder()
    register_login_throttling(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginThrottlingConfig(secret="counting"),
        lock_active=True,
    )
    factory = recorder.factories[0]

    listener = factory(
        InMemoryStorage(),
        clock=None,
        firewall_dispatcher=None,
        lock_factory=LockFactory(InMemoryStore()),
    )

    assert factory.__annotations__["lock_factory"] == LockFactory | None
    assert isinstance(listener, LoginThrottlingListener)


def test_a_channel_rule_naming_an_unknown_scheme_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match='neither "http" nor "https"'):
        _ = AccessControlConfig(path=r"^/", attribute="PUBLIC_ACCESS", channel="ftp")


def test_a_channel_rule_naming_https_is_answered_by_the_map() -> None:
    rule = AccessControlConfig(path=r"^/", attribute="PUBLIC_ACCESS", channel="https")

    assert rule.channel == "https"


@pytest.mark.anyio
async def test_the_channel_step_is_built_once_for_the_application() -> None:
    """It holds only the firewall's rules and what it answers with: nothing of a request."""
    kernel = Kernel("tests.fixtures.remember_me_app", env="test", bundles=BUNDLES)
    qualifier = firewall_channel_listener_name("main")

    async with await kernel.boot() as booted:
        first = await booted.container.get(ChannelListener, qualifier)
        again = await booted.container.get(ChannelListener, qualifier)

    assert first is again
