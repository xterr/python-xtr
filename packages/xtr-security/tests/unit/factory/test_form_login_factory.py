"""The form-login factory builds a firewall's form login from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_http_message_contracts import ServerRequestInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    CustomAuthenticationFailureHandler,
    CustomAuthenticationSuccessHandler,
    DefaultAuthenticationFailureHandler,
    DefaultAuthenticationSuccessHandler,
    FormLoginAuthenticator,
    HttpUtils,
)

from xtr_security.bundle import FormLoginConfig
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AuthenticatorFactoryInterface, FormLoginFactory

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
    """A stand-in configurator recording every ``set`` the factory makes."""

    def __init__(self) -> None:
        self.factories: list[Callable[..., object]] = []
        self.qualifiers: list[Hashable | None] = []

    def set(
        self,
        target: Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> _RecordingDefinition:
        del lifetime
        self.factories.append(target)
        self.qualifiers.append(qualifier)
        return _RecordingDefinition(cast("ServiceKey", (object, qualifier)))


def test_it_carries_its_interface_key_and_config() -> None:
    factory = FormLoginFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "form_login"
    assert factory.config_type is FormLoginConfig
    assert isinstance(factory.priority, int)
    assert factory.entry_point_kind(FormLoginConfig(login_path="/login")) == "real"


def test_a_form_login_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = FormLoginFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api",
            FormLoginConfig(login_path="/login"),
            None,
        )


def test_it_builds_the_default_handler_pair_and_the_authenticator() -> None:
    recorder = _Recorder()

    keys = FormLoginFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FormLoginConfig(login_path="/login", check_path="/login_check"),
        (UserProviderInterface, "users"),
    )

    assert [qualifier for qualifier in recorder.qualifiers if qualifier is not None] == [
        "main#form_login_success_handler",
        "main#form_login_failure_handler",
        "main",
    ]
    assert keys[-1] == (object, "main")

    http_utils = HttpUtils(ResponseFactory())
    success_handler = recorder.factories[0](http_utils=http_utils)
    assert isinstance(success_handler, DefaultAuthenticationSuccessHandler)
    assert success_handler.get_firewall_name() == "main"
    assert success_handler.get_options()["login_path"] == "/login"

    failure_handler = recorder.factories[1](http_utils=http_utils)
    assert isinstance(failure_handler, DefaultAuthenticationFailureHandler)

    authenticator = recorder.factories[2](
        http_utils=http_utils,
        provider=cast("UserProviderInterface", object()),
        success_handler=success_handler,
        failure_handler=failure_handler,
    )
    assert isinstance(authenticator, FormLoginAuthenticator)
    assert authenticator.get_login_url(cast("ServerRequestInterface", object())) == "/login"


def test_the_configured_handlers_are_wrapped_in_the_custom_pair() -> None:
    recorder = _Recorder()

    class _UserSuccessHandler:
        pass

    class _UserFailureHandler:
        pass

    _ = FormLoginFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        FormLoginConfig(
            login_path="/login",
            success_handler=_UserSuccessHandler,
            failure_handler=_UserFailureHandler,
        ),
        (UserProviderInterface, "users"),
    )

    assert recorder.factories[0].__annotations__["handler"] is _UserSuccessHandler
    success_handler = recorder.factories[0](handler=object())
    assert isinstance(success_handler, CustomAuthenticationSuccessHandler)

    assert recorder.factories[1].__annotations__["handler"] is _UserFailureHandler
    failure_handler = recorder.factories[1](handler=object())
    assert isinstance(failure_handler, CustomAuthenticationFailureHandler)
