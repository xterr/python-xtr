"""The factory that builds a firewall's login-link authenticator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import Target
from xtr_security_core import SignatureHasher
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_http import (
    CustomAuthenticationFailureHandler,
    CustomAuthenticationSuccessHandler,
    DefaultAuthenticationFailureHandler,
    DefaultAuthenticationSuccessHandler,
    HttpUtils,
    LoginLinkAuthenticator,
    LoginLinkHandler,
    LoginLinkHandlerInterface,
)

from xtr_security.bundle.login_link_config import LoginLinkConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_security_http.authentication.authentication_failure_handler_interface import (
        AuthenticationFailureHandlerInterface,
    )
    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )

__all__ = ["LoginLinkFactory", "login_link_handler_name"]


def login_link_handler_name(firewall_name: str) -> str:
    """The qualifier of a firewall's login-link handler service."""
    return f"{firewall_name}#login_link_handler"


@final
class LoginLinkFactory(AuthenticatorFactoryInterface):
    """Builds a :class:`~xtr_security_http.LoginLinkAuthenticator` from configuration.

    The handler that mints and spends the links is a service of the
    firewall's own, signing each over the user's covered properties until a
    lifetime from when it was minted. The secret the link is signed with is
    the application's to supply: the bundle builds and boots without it, and
    the handler fails naming it the first time it is asked for. The
    authenticator itself never challenges: a request that follows no link
    has nothing to spend, so it is no entry point.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``login_link``."""
        return "login_link"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return 0

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`LoginLinkConfig`."""
        return LoginLinkConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that a followed link never answers an unauthenticated request."""
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
        """Register the handler, the answer handlers and the authenticator over them."""
        del builder
        settings = cast("LoginLinkConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'A login link on the firewall "{firewall_name}" needs a user provider; '
                f"name one on the firewall.",
            )

        handler_key = _register_handler(services, firewall_name, settings, user_provider)
        success_key = _register_success_handler(services, firewall_name, settings)
        failure_key = _register_failure_handler(services, firewall_name, settings)
        handler_annotation = Annotated[handler_key[0], Target(handler_key[1])]  # ty: ignore[invalid-type-form] -- runtime marker

        def login_link_authenticator(
            handler: object,
            http_utils: HttpUtils,
            success_handler: object,
            failure_handler: object,
        ) -> LoginLinkAuthenticator:
            """Build the authenticator spending links through its firewall's handler."""
            return LoginLinkAuthenticator(
                cast("LoginLinkHandlerInterface", handler),
                http_utils,
                cast("AuthenticationSuccessHandlerInterface", success_handler),
                cast("AuthenticationFailureHandlerInterface", failure_handler),
                {
                    "check_path": settings.check_path,
                    "check_post_only": settings.check_post_only,
                },
            )

        login_link_authenticator.__annotations__ = {
            "handler": handler_annotation,
            "http_utils": HttpUtils,
            "success_handler": Annotated[success_key[0], Target(success_key[1])],  # ty: ignore[invalid-type-form] -- runtime marker
            "failure_handler": Annotated[failure_key[0], Target(failure_key[1])],  # ty: ignore[invalid-type-form] -- runtime marker
            "return": LoginLinkAuthenticator,
        }
        login_link_authenticator.__name__ = f"login_link_authenticator_{firewall_name}"
        login_link_authenticator.__qualname__ = login_link_authenticator.__name__
        return (services.set(login_link_authenticator, qualifier=firewall_name).key,)


def _register_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: LoginLinkConfig,
    user_provider: ServiceKey,
) -> ServiceKey:
    """Register the handler a firewall's minted links are signed by."""

    def login_link_handler(
        provider: UserProviderInterface,
        clock: ClockInterface | None = None,
    ) -> LoginLinkHandler:
        """Build the handler signing links until a lifetime from their minting."""
        if not settings.secret:
            raise InvalidConfigurationError(
                f'The login link of the firewall "{firewall_name}" signs its links with a '
                f'"secret" the application must supply; set one on the login-link '
                f"configuration.",
            )
        return LoginLinkHandler(
            provider,
            SignatureHasher(tuple(settings.signature_properties), settings.secret),
            {"path": settings.path, "lifetime": settings.lifetime},
            clock=clock,
        )

    login_link_handler.__annotations__ = {
        "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
        "clock": ClockInterface | None,
        "return": LoginLinkHandler,
    }
    login_link_handler.__name__ = f"login_link_handler_{firewall_name}"
    login_link_handler.__qualname__ = login_link_handler.__name__
    return services.set(login_link_handler, qualifier=login_link_handler_name(firewall_name)).key


def _register_success_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: LoginLinkConfig,
) -> ServiceKey:
    """Register the handler a successful login link is answered by."""
    if settings.success_handler is None:

        def default_success_handler(
            http_utils: HttpUtils,
        ) -> DefaultAuthenticationSuccessHandler:
            handler = DefaultAuthenticationSuccessHandler(http_utils, {})
            handler.set_firewall_name(firewall_name)
            return handler

        default_success_handler.__annotations__ = {
            "http_utils": HttpUtils,
            "return": DefaultAuthenticationSuccessHandler,
        }
        success_handler = default_success_handler
    else:

        def wrapped_success_handler(
            handler: object,
        ) -> CustomAuthenticationSuccessHandler:
            return CustomAuthenticationSuccessHandler(
                cast("AuthenticationSuccessHandlerInterface", handler),
                {},
                firewall_name,
            )

        wrapped_success_handler.__annotations__ = {
            "handler": settings.success_handler,
            "return": CustomAuthenticationSuccessHandler,
        }
        success_handler = wrapped_success_handler

    success_handler.__name__ = f"login_link_success_handler_{firewall_name}"
    success_handler.__qualname__ = success_handler.__name__
    return services.set(
        success_handler, qualifier=f"{firewall_name}#login_link_success_handler"
    ).key


def _register_failure_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: LoginLinkConfig,
) -> ServiceKey:
    """Register the handler a failed login link is answered by."""
    if settings.failure_handler is None:

        def default_failure_handler(
            http_utils: HttpUtils,
        ) -> DefaultAuthenticationFailureHandler:
            return DefaultAuthenticationFailureHandler(http_utils, {}, firewall_name=firewall_name)

        default_failure_handler.__annotations__ = {
            "http_utils": HttpUtils,
            "return": DefaultAuthenticationFailureHandler,
        }
        failure_handler = default_failure_handler
    else:

        def wrapped_failure_handler(
            handler: object,
        ) -> CustomAuthenticationFailureHandler:
            return CustomAuthenticationFailureHandler(
                cast("AuthenticationFailureHandlerInterface", handler),
                {},
            )

        wrapped_failure_handler.__annotations__ = {
            "handler": settings.failure_handler,
            "return": CustomAuthenticationFailureHandler,
        }
        failure_handler = wrapped_failure_handler

    failure_handler.__name__ = f"login_link_failure_handler_{firewall_name}"
    failure_handler.__qualname__ = failure_handler.__name__
    return services.set(
        failure_handler, qualifier=f"{firewall_name}#login_link_failure_handler"
    ).key
