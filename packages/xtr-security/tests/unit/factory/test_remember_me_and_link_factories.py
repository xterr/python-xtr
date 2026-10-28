"""The remember-me, login-link and pre-authenticated factories build from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface
from xtr_security_http import (
    LoginLinkAuthenticator,
    LoginLinkHandler,
    RememberMeAuthenticator,
    RemoteUserAuthenticator,
    SignatureRememberMeHandler,
    X509Authenticator,
)

from xtr_security.bundle import (
    LoginLinkConfig,
    RememberMeConfig,
    RemoteUserConfig,
    X509Config,
)
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import (
    AuthenticatorFactoryInterface,
    LoginLinkFactory,
    RememberMeFactory,
    RemoteUserFactory,
    X509Factory,
)
from xtr_security.factory.remember_me_factory import remember_me_handler_name

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


_PROVIDER = cast("ServiceKey", (UserProviderInterface, "users"))


def test_the_remember_me_factory_answers_its_interface_shape() -> None:
    factory = RememberMeFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "remember_me"
    assert factory.config_type is RememberMeConfig
    assert factory.priority < 0
    assert factory.entry_point_kind(RememberMeConfig()) == "none"


def test_the_remember_me_factory_registers_handler_and_authenticator() -> None:
    recorder = _Recorder()

    keys = RememberMeFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        RememberMeConfig(secret="signed"),
        _PROVIDER,
    )

    assert len(keys) == 1
    assert recorder.qualifiers == [remember_me_handler_name("main"), "main"]
    handler = recorder.factories[0]
    provider = _Provider()
    built_handler = handler(provider, clock=None)
    assert isinstance(built_handler, SignatureRememberMeHandler)
    authenticator = recorder.factories[1](built_handler, _Storage())
    assert isinstance(authenticator, RememberMeAuthenticator)


def test_the_remember_me_handler_fails_naming_the_secret_when_it_is_absent() -> None:
    recorder = _Recorder()

    _ = RememberMeFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        RememberMeConfig(),
        _PROVIDER,
    )

    with pytest.raises(InvalidConfigurationError, match='"secret"'):
        _ = recorder.factories[0](_Provider(), clock=None)


def test_the_persistent_handler_fails_naming_its_token_provider_when_absent() -> None:
    with pytest.raises(InvalidConfigurationError, match='"token_provider"'):
        _ = RememberMeFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            RememberMeConfig(handler="persistent"),
            _PROVIDER,
        )


def test_the_persistent_handler_builds_over_the_application_token_provider() -> None:
    from xtr_security_http import PersistentRememberMeHandler

    recorder = _Recorder()

    _ = RememberMeFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        RememberMeConfig(handler="persistent", secret="signed", token_provider="tokens"),
        _PROVIDER,
    )

    handler = recorder.factories[0](_Provider(), _Tokens(), clock=None)
    assert isinstance(handler, PersistentRememberMeHandler)


def test_the_persistent_handler_fails_naming_the_secret_when_it_is_absent() -> None:
    recorder = _Recorder()

    _ = RememberMeFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        RememberMeConfig(handler="persistent", token_provider="tokens"),
        _PROVIDER,
    )

    with pytest.raises(InvalidConfigurationError, match='"secret"'):
        _ = recorder.factories[0](_Provider(), _Tokens(), clock=None)


def test_a_login_link_wraps_the_application_handlers_it_is_given() -> None:
    from xtr_security_http import (
        CustomAuthenticationFailureHandler,
        CustomAuthenticationSuccessHandler,
    )

    recorder = _Recorder()

    _ = LoginLinkFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginLinkConfig(
            check_path="/login_link",
            path="/login",
            secret="signed",
            success_handler=_Success,
            failure_handler=_Failure,
        ),
        _PROVIDER,
    )

    assert isinstance(recorder.factories[1](_Success()), CustomAuthenticationSuccessHandler)
    assert isinstance(recorder.factories[2](_Failure()), CustomAuthenticationFailureHandler)


def test_a_remember_me_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="user provider"):
        _ = RememberMeFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            RememberMeConfig(),
            None,
        )


def test_the_login_link_factory_answers_its_interface_shape() -> None:
    factory = LoginLinkFactory()

    assert factory.key == "login_link"
    assert factory.config_type is LoginLinkConfig
    assert factory.entry_point_kind(LoginLinkConfig(check_path="/l", path="/l")) == "none"


def test_the_login_link_factory_registers_handler_and_authenticator() -> None:
    recorder = _Recorder()

    keys = LoginLinkFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginLinkConfig(check_path="/login_link", path="/login", secret="signed"),
        _PROVIDER,
    )

    assert len(keys) == 1
    handler = recorder.factories[0]
    assert isinstance(handler(_Provider(), clock=None), LoginLinkHandler)
    authenticator = recorder.factories[3](
        handler(_Provider(), clock=None), _Utils(), _Success(), _Failure()
    )
    assert isinstance(authenticator, LoginLinkAuthenticator)


def test_the_login_link_handler_fails_naming_the_secret_when_it_is_absent() -> None:
    recorder = _Recorder()

    _ = LoginLinkFactory().create_authenticator(
        recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        LoginLinkConfig(check_path="/login_link", path="/login"),
        _PROVIDER,
    )

    with pytest.raises(InvalidConfigurationError, match='"secret"'):
        _ = recorder.factories[0](_Provider(), clock=None)


def test_the_pre_authenticated_factories_answer_their_interface_shape() -> None:
    remote = RemoteUserFactory()
    x509 = X509Factory()

    assert remote.key == "remote_user"
    assert remote.config_type is RemoteUserConfig
    assert x509.key == "x509"
    assert x509.config_type is X509Config
    assert remote.priority > 0
    assert remote.entry_point_kind(RemoteUserConfig()) == "none"
    assert x509.priority == remote.priority
    assert x509.entry_point_kind(X509Config()) == "none"


def test_the_pre_authenticated_factories_register_their_authenticators() -> None:
    remote_recorder = _Recorder()
    x509_recorder = _Recorder()

    _ = RemoteUserFactory().create_authenticator(
        remote_recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        RemoteUserConfig(),
        _PROVIDER,
    )
    _ = X509Factory().create_authenticator(
        x509_recorder,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "main",
        X509Config(),
        _PROVIDER,
    )

    assert isinstance(
        remote_recorder.factories[0](_Provider(), _Storage()),
        RemoteUserAuthenticator,
    )
    assert isinstance(x509_recorder.factories[0](_Provider(), _Storage()), X509Authenticator)


def test_a_pre_authenticated_authenticator_without_a_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="user provider"):
        _ = RemoteUserFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            X509Config(),
            None,
        )


def test_a_login_link_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="user provider"):
        _ = LoginLinkFactory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            LoginLinkConfig(check_path="/login_link", path="/login"),
            None,
        )


def test_an_x509_authenticator_without_a_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="user provider"):
        _ = X509Factory().create_authenticator(
            _Recorder(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "main",
            RemoteUserConfig(),
            None,
        )


@final
class _Provider(UserProviderInterface):
    """A stand-in provider."""

    __slots__: tuple[str, ...] = ()

    @override
    async def refresh_user(self, user: UserInterface) -> UserInterface:
        del user
        raise NotImplementedError

    @override
    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        del identifier
        raise NotImplementedError

    @override
    def supports_class(self, user_class: type) -> bool:
        del user_class
        return True


@final
class _Storage:
    """A stand-in token storage."""

    __slots__ = ()


@final
class _Utils:
    """A stand-in HTTP utils."""

    __slots__ = ()


@final
class _Success:
    """A stand-in success handler."""

    __slots__ = ()


@final
class _Failure:
    """A stand-in failure handler."""

    __slots__ = ()


@final
class _Tokens:
    """A stand-in token-provider service."""

    __slots__ = ()
