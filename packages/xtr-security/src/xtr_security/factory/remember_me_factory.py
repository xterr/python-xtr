"""The factory that builds a firewall's remember-me authenticator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import Target
from xtr_security_core import SignatureHasher, TokenStorageInterface
from xtr_security_core.authentication.remember_me.token_provider_interface import (
    TokenProviderInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_http import (
    PersistentRememberMeHandler,
    RememberMeAuthenticator,
    RememberMeHandlerInterface,
    SignatureRememberMeHandler,
)

from xtr_security.bundle.remember_me_config import RememberMeConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["RememberMeFactory", "remember_me_handler_name"]


def remember_me_handler_name(firewall_name: str) -> str:
    """The qualifier of a firewall's remember-me handler service."""
    return f"{firewall_name}#remember_me_handler"


@final
class RememberMeFactory(AuthenticatorFactoryInterface):
    """Builds a :class:`~xtr_security_http.RememberMeAuthenticator` from configuration.

    The handler the authenticator spends cookies through is a service of the
    firewall's own — signed over the user's covered properties, or persisted
    as a series the application's token provider keeps — registered under
    the qualifier the firewall's listeners reach it by. The secret the value
    is signed with is the application's to supply: the bundle builds and
    boots without it, and the handler fails naming it the first time it is
    asked for. The authenticator itself never challenges: a request that
    presents no cookie has nothing to spend, so it is no entry point.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``remember_me``."""
        return "remember_me"

    @property
    @override
    def priority(self) -> int:
        """Run behind the authenticators that log a request in.

        The cookie this authenticator spends must not preempt one: its
        supports guard refuses a request whose storage already holds a
        token, and the session-restoring steps and the logins the request
        itself brings run first, so a lower priority keeps the remembered
        login from answering where a fresher one already has.
        """
        return -100

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`RememberMeConfig`."""
        return RememberMeConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that a remembered login never answers an unauthenticated request."""
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
        """Register the handler and the authenticator over the firewall's provider."""
        del builder
        settings = cast("RememberMeConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'A remember-me authenticator on the firewall "{firewall_name}" needs a '
                f"user provider; name one on the firewall.",
            )

        handler_key = _register_handler(services, firewall_name, settings, user_provider)
        handler_annotation = Annotated[handler_key[0], Target(handler_key[1])]  # ty: ignore[invalid-type-form] -- runtime marker

        def remember_me_authenticator(
            handler: object,
            token_storage: TokenStorageInterface,
        ) -> RememberMeAuthenticator:
            """Build the authenticator spending cookies through its firewall's handler."""
            return RememberMeAuthenticator(
                cast("RememberMeHandlerInterface", handler),
                token_storage,
                settings.name,
            )

        remember_me_authenticator.__annotations__ = {
            "handler": handler_annotation,
            "token_storage": TokenStorageInterface,
            "return": RememberMeAuthenticator,
        }
        remember_me_authenticator.__name__ = f"remember_me_authenticator_{firewall_name}"
        remember_me_authenticator.__qualname__ = remember_me_authenticator.__name__
        return (
            services.set(remember_me_authenticator, qualifier=firewall_name, lifetime="scoped").key,
        )


def _register_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: RememberMeConfig,
    user_provider: ServiceKey,
) -> ServiceKey:
    """Register the handler a firewall's remember-me cookies live in."""
    options = settings.to_options()
    signature_properties = (
        tuple(settings.signature_properties)
        if settings.signature_properties is not None
        else ("password",)
    )

    def _check_secret() -> None:
        """Refuse a signing secret the application never supplied."""
        if not settings.secret:
            raise InvalidConfigurationError(
                f'The remember-me authenticator of the firewall "{firewall_name}" signs its '
                f'cookies with a "secret" the application must supply; set one on the '
                f"remember-me configuration.",
            )

    if settings.handler == "signature":

        def signature_handler(
            provider: UserProviderInterface,
            clock: ClockInterface | None = None,
        ) -> SignatureRememberMeHandler:
            """Build the handler signing cookies over the covered properties."""
            _check_secret()
            return SignatureRememberMeHandler(
                SignatureHasher(signature_properties, cast("str", settings.secret), clock),
                provider,
                options,
                clock=clock,
            )

        signature_handler.__annotations__ = {
            "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
            "clock": ClockInterface | None,
            "return": SignatureRememberMeHandler,
        }
        signature_handler.__name__ = f"remember_me_handler_{firewall_name}"
        signature_handler.__qualname__ = signature_handler.__name__
        return services.set(
            signature_handler, qualifier=remember_me_handler_name(firewall_name)
        ).key

    if settings.token_provider is None:
        raise InvalidConfigurationError(
            f'The persistent remember-me handler of the firewall "{firewall_name}" keeps its '
            f'series in a "token_provider" service the application must supply; name one on '
            f"the remember-me configuration.",
        )

    def persistent_handler(
        provider: UserProviderInterface,
        token_provider: Annotated[TokenProviderInterface, Target(settings.token_provider)],
        clock: ClockInterface | None = None,
    ) -> PersistentRememberMeHandler:
        """Build the handler keeping its series in the application's token provider."""
        _check_secret()
        return PersistentRememberMeHandler(
            token_provider,
            provider,
            options,
            signature_properties=signature_properties,
            clock=clock,
        )

    persistent_handler.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
        "token_provider": Annotated[TokenProviderInterface, Target(settings.token_provider)],
        "clock": ClockInterface | None,
        "return": PersistentRememberMeHandler,
    }
    persistent_handler.__name__ = f"remember_me_handler_{firewall_name}"
    persistent_handler.__qualname__ = persistent_handler.__name__
    return services.set(persistent_handler, qualifier=remember_me_handler_name(firewall_name)).key
