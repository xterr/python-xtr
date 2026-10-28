"""The HTTP basic factory builds the browser's own credential prompt."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import HttpBasicAuthenticator

from xtr_security.bundle import HttpBasicConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AuthenticatorFactoryInterface, HttpBasicFactory

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable

    from xtr_dependency_injection import ServiceKey


@final
class _RecordingDefinition:
    """A stand-in definition handing back the key of the service it describes."""

    def __init__(self, key: ServiceKey) -> None:
        self.key = key


@final
class _Recorder:
    """A stand-in configurator recording the one ``set`` the factory makes."""

    def __init__(self) -> None:
        self.factory: Callable[..., object] | None = None
        self.qualifier: Hashable | None = None

    def set(
        self,
        target: Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> _RecordingDefinition:
        del lifetime
        self.factory = target
        self.qualifier = qualifier
        return _RecordingDefinition(cast("ServiceKey", (object, qualifier)))


def test_it_carries_its_interface_key_and_config() -> None:
    factory = HttpBasicFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "http_basic"
    assert factory.config_type is HttpBasicConfig
    assert isinstance(factory.priority, int)
    assert factory.entry_point_kind(HttpBasicConfig()) == "real"


def test_an_authenticator_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = HttpBasicFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api",
            HttpBasicConfig(),
            None,
        )


def test_it_builds_an_http_basic_authenticator() -> None:
    recorder = _Recorder()

    keys = HttpBasicFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api",
        HttpBasicConfig(realm="api"),
        (UserProviderInterface, "users"),
    )

    assert keys[0] == (object, "api")
    assert recorder.qualifier == "api"
    assert recorder.factory is not None
    authenticator = recorder.factory(
        provider=cast("UserProviderInterface", object()),
        responses=ResponseFactory(),
    )
    assert isinstance(authenticator, HttpBasicAuthenticator)
