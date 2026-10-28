"""The JSON-login factory builds a firewall's JSON login from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import HttpUtils, JsonLoginAuthenticator

from xtr_security.bundle import JsonLoginConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AuthenticatorFactoryInterface, JsonLoginFactory

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
    factory = JsonLoginFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "json_login"
    assert factory.config_type is JsonLoginConfig
    assert isinstance(factory.priority, int)
    # The landed authenticator is no entry point: it implements no entry
    # point interface and starts nothing, so it never challenges.
    assert factory.entry_point_kind(JsonLoginConfig()) == "none"


def test_a_json_login_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = JsonLoginFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api",
            JsonLoginConfig(),
            None,
        )


def test_it_builds_a_json_login_authenticator_without_configured_handlers() -> None:
    recorder = _Recorder()

    keys = JsonLoginFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api",
        JsonLoginConfig(check_path="/api/login"),
        (UserProviderInterface, "users"),
    )

    assert keys[0] == (object, "api")
    assert recorder.qualifier == "api"
    assert recorder.factory is not None
    assert "success_handler" not in recorder.factory.__annotations__
    assert "failure_handler" not in recorder.factory.__annotations__
    authenticator = recorder.factory(
        http_utils=HttpUtils(ResponseFactory()),
        provider=cast("UserProviderInterface", object()),
        responses=ResponseFactory(),
    )
    assert isinstance(authenticator, JsonLoginAuthenticator)


def test_the_configured_handlers_reach_the_authenticator() -> None:
    recorder = _Recorder()

    class _UserSuccessHandler:
        pass

    class _UserFailureHandler:
        pass

    _ = JsonLoginFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api",
        JsonLoginConfig(
            success_handler=_UserSuccessHandler,
            failure_handler=_UserFailureHandler,
        ),
        (UserProviderInterface, "users"),
    )

    assert recorder.factory.__annotations__["success_handler"] is _UserSuccessHandler
    assert recorder.factory.__annotations__["failure_handler"] is _UserFailureHandler
