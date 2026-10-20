"""The factory that builds a firewall's form login from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_security_core.user.user_provider_interface import (  # noqa: TC002 -- a factory signature the container reads
    UserProviderInterface,
)
from xtr_security_http import HttpUtils
from xtr_security_http.authentication.authentication_failure_handler_interface import (  # noqa: TC002 -- a factory signature the container reads
    AuthenticationFailureHandlerInterface,
)
from xtr_security_http.authentication.authentication_success_handler_interface import (  # noqa: TC002 -- a factory signature the container reads
    AuthenticationSuccessHandlerInterface,
)

from xtr_security.bundle.authenticator_configs import FormLoginConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["FormLoginFactory"]


@final
class FormLoginFactory(AuthenticatorFactoryInterface):
    """Builds a :class:`~xtr_security_http.FormLoginAuthenticator` from configuration.

    The form is rendered at the configured login path and submitted to the
    check path; a failed login is stored on the session and redirected back
    to the page, a successful one answered by the target ladder — the
    default pair of handlers, or the application's own pair wrapped in the
    custom pair when the configuration names them. The redirect to the login
    page is a real entry point: an unauthenticated request is sent there to
    prove itself.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``form_login``."""
        return "form_login"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return 0

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`FormLoginConfig`."""
        return FormLoginConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that the redirect to the login page is a real entry point."""
        del config
        return "real"

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the login's handlers and the authenticator over them."""
        del builder
        settings = cast("FormLoginConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'A form login on the firewall "{firewall_name}" needs a user provider; '
                f"name one on the firewall.",
            )

        success_key = _register_success_handler(services, firewall_name, settings)
        failure_key = _register_failure_handler(services, firewall_name, settings)
        return (
            _register_authenticator(
                services, firewall_name, settings, user_provider, success_key, failure_key
            ),
        )


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names."""
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def _register_success_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: FormLoginConfig,
) -> ServiceKey:
    """Register the handler a successful login is answered by."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's login import
        CustomAuthenticationSuccessHandler,
        DefaultAuthenticationSuccessHandler,
    )

    options = {"login_path": settings.login_path}

    if settings.success_handler is None:

        def default_success_handler(
            http_utils: HttpUtils,
        ) -> DefaultAuthenticationSuccessHandler:
            handler = DefaultAuthenticationSuccessHandler(http_utils, options)
            handler.set_firewall_name(firewall_name)
            return handler

        default_success_handler.__annotations__ = {
            "http_utils": HttpUtils,
            "return": DefaultAuthenticationSuccessHandler,
        }
        success_handler: Callable[..., object] = default_success_handler
    else:

        def wrapped_success_handler(
            handler: object,
        ) -> CustomAuthenticationSuccessHandler:
            return CustomAuthenticationSuccessHandler(
                cast("AuthenticationSuccessHandlerInterface", handler),
                options,
                firewall_name,
            )

        wrapped_success_handler.__annotations__ = {
            "handler": settings.success_handler,
            "return": CustomAuthenticationSuccessHandler,
        }
        success_handler = wrapped_success_handler

    success_handler.__name__ = f"form_login_success_handler_{firewall_name}"
    success_handler.__qualname__ = success_handler.__name__
    return services.set(
        success_handler, qualifier=f"{firewall_name}#form_login_success_handler"
    ).key


def _register_failure_handler(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: FormLoginConfig,
) -> ServiceKey:
    """Register the handler a failed login is answered by."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's login import
        CustomAuthenticationFailureHandler,
        DefaultAuthenticationFailureHandler,
    )

    options = {"login_path": settings.login_path}

    if settings.failure_handler is None:

        def default_failure_handler(
            http_utils: HttpUtils,
        ) -> DefaultAuthenticationFailureHandler:
            return DefaultAuthenticationFailureHandler(
                http_utils, options, firewall_name=firewall_name
            )

        default_failure_handler.__annotations__ = {
            "http_utils": HttpUtils,
            "return": DefaultAuthenticationFailureHandler,
        }
        failure_handler: Callable[..., object] = default_failure_handler
    else:

        def wrapped_failure_handler(
            handler: object,
        ) -> CustomAuthenticationFailureHandler:
            return CustomAuthenticationFailureHandler(
                cast("AuthenticationFailureHandlerInterface", handler),
                options,
            )

        wrapped_failure_handler.__annotations__ = {
            "handler": settings.failure_handler,
            "return": CustomAuthenticationFailureHandler,
        }
        failure_handler = wrapped_failure_handler

    failure_handler.__name__ = f"form_login_failure_handler_{firewall_name}"
    failure_handler.__qualname__ = failure_handler.__name__
    return services.set(
        failure_handler, qualifier=f"{firewall_name}#form_login_failure_handler"
    ).key


def _register_authenticator(  # noqa: PLR0913, PLR0917 -- one login from its firewall's parts
    services: ServiceConfigurator,
    firewall_name: str,
    settings: FormLoginConfig,
    user_provider: ServiceKey,
    success_key: ServiceKey,
    failure_key: ServiceKey,
) -> ServiceKey:
    """Register the authenticator over the firewall's provider and handlers."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's login import
        FormLoginAuthenticator,
    )

    options = {
        "login_path": settings.login_path,
        "check_path": settings.check_path,
        "username_parameter": settings.username_parameter,
        "password_parameter": settings.password_parameter,
        "post_only": settings.post_only,
        "form_only": settings.form_only,
        "enable_csrf": settings.enable_csrf,
        "csrf_parameter": settings.csrf_parameter,
        "csrf_token_id": settings.csrf_token_id,
    }

    def form_login_authenticator(
        http_utils: HttpUtils,
        provider: UserProviderInterface,
        success_handler: object,
        failure_handler: object,
    ) -> FormLoginAuthenticator:
        return FormLoginAuthenticator(
            http_utils,
            provider,
            cast("AuthenticationSuccessHandlerInterface", success_handler),
            cast("AuthenticationFailureHandlerInterface", failure_handler),
            options,
        )

    form_login_authenticator.__annotations__ = {
        "http_utils": HttpUtils,
        "provider": _qualified(user_provider),
        "success_handler": _qualified(success_key),
        "failure_handler": _qualified(failure_key),
        "return": FormLoginAuthenticator,
    }
    form_login_authenticator.__name__ = f"form_login_authenticator_{firewall_name}"
    form_login_authenticator.__qualname__ = form_login_authenticator.__name__
    return services.set(form_login_authenticator, qualifier=firewall_name).key
