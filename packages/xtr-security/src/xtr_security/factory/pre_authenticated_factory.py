"""The factories that build a firewall's pre-authenticated authenticators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_security_core import TokenStorageInterface
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_http import RemoteUserAuthenticator, X509Authenticator

from xtr_security.bundle.pre_authenticated_configs import RemoteUserConfig, X509Config
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["RemoteUserFactory", "X509Factory"]

_PRE_AUTHENTICATED_PRIORITY = 100
"""Ahead of the interactive logins a pre-authenticated request never reaches."""


@final
class RemoteUserFactory(AuthenticatorFactoryInterface):
    """Builds a :class:`~xtr_security_http.RemoteUserAuthenticator` from configuration.

    The request arrives already authenticated by the server in front of the
    application, so the authenticator only reads the account that server
    named; it never challenges, because a request with nothing to read is
    not a request this kind of proof answers.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``remote_user``."""
        return "remote_user"

    @property
    @override
    def priority(self) -> int:
        """Run ahead of the interactive logins a pre-authenticated request never reaches."""
        return _PRE_AUTHENTICATED_PRIORITY

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`RemoteUserConfig`."""
        return RemoteUserConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that a pre-authenticated proof never answers an unauthenticated request."""
        del config
        return "none"

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the authenticator reading the account the server in front named."""
        del builder
        settings = cast("RemoteUserConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'A remote-user authenticator on the firewall "{firewall_name}" needs a user '
                f"provider; name one on the firewall.",
            )

        return (
            _register_remote_user_authenticator(services, firewall_name, settings, user_provider),
        )


def _register_remote_user_authenticator(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: RemoteUserConfig,
    user_provider: ServiceKey,
) -> ServiceKey:
    """Register the authenticator reading the account the server in front named."""

    def remote_user_authenticator(
        provider: Annotated[UserProviderInterface, Target(user_provider[1])],
        token_storage: TokenStorageInterface,
    ) -> RemoteUserAuthenticator:
        return RemoteUserAuthenticator(provider, token_storage, firewall_name, settings.user_key)

    remote_user_authenticator.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
        "token_storage": TokenStorageInterface,
        "return": RemoteUserAuthenticator,
    }
    remote_user_authenticator.__name__ = f"remote_user_authenticator_{firewall_name}"
    remote_user_authenticator.__qualname__ = remote_user_authenticator.__name__
    return services.set(remote_user_authenticator, qualifier=firewall_name, lifetime="scoped").key


@final
class X509Factory(AuthenticatorFactoryInterface):
    """Builds an :class:`~xtr_security_http.X509Authenticator` from configuration.

    The request arrives already authenticated by the client's own
    certificate, so the authenticator only reads the identifier that
    certificate named; it never challenges, because a request with nothing
    to read is not a request this kind of proof answers.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``x509``."""
        return "x509"

    @property
    @override
    def priority(self) -> int:
        """Run ahead of the interactive logins a pre-authenticated request never reaches."""
        return _PRE_AUTHENTICATED_PRIORITY

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`X509Config`."""
        return X509Config

    def entry_point_kind(self, config: object) -> str:
        """Answer that a pre-authenticated proof never answers an unauthenticated request."""
        del config
        return "none"

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the authenticator reading the client's own certificate."""
        del builder
        settings = cast("X509Config", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'An x509 authenticator on the firewall "{firewall_name}" needs a user '
                f"provider; name one on the firewall.",
            )

        return (_register_x509_authenticator(services, firewall_name, settings, user_provider),)


def _register_x509_authenticator(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: X509Config,
    user_provider: ServiceKey,
) -> ServiceKey:
    """Register the authenticator reading the client's own certificate."""

    def x509_authenticator(
        provider: Annotated[UserProviderInterface, Target(user_provider[1])],
        token_storage: TokenStorageInterface,
    ) -> X509Authenticator:
        return X509Authenticator(
            provider,
            token_storage,
            firewall_name,
            settings.user_key,
            settings.credentials_key,
            credential_user_identifier=settings.credential_user_identifier,
        )

    x509_authenticator.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
        "token_storage": TokenStorageInterface,
        "return": X509Authenticator,
    }
    x509_authenticator.__name__ = f"x509_authenticator_{firewall_name}"
    x509_authenticator.__qualname__ = x509_authenticator.__name__
    return services.set(x509_authenticator, qualifier=firewall_name, lifetime="scoped").key
