"""The factory that builds a firewall's JSON login from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_http import HttpUtils, JsonLoginAuthenticator
from xtr_security_http.authentication.authentication_failure_handler_interface import (  # noqa: TC002 -- a factory signature the container reads
    AuthenticationFailureHandlerInterface,
)
from xtr_security_http.authentication.authentication_success_handler_interface import (  # noqa: TC002 -- a factory signature the container reads
    AuthenticationSuccessHandlerInterface,
)

from xtr_security.bundle.authenticator_configs import JsonLoginConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["JsonLoginFactory"]


@final
class JsonLoginFactory(AuthenticatorFactoryInterface):
    """Builds a :class:`~xtr_security_http.JsonLoginAuthenticator` from configuration.

    The document is the request's parsed body, its two members read by the
    dotted paths the configuration names. The login never challenges: it is
    no entry point — an unauthenticated request is not answered by it, only
    a request carrying a document is — so a firewall whose only login is
    this one resolves its entry point elsewhere, and a firewall that needs
    authentication must name one.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``json_login``."""
        return "json_login"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return 0

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`JsonLoginConfig`."""
        return JsonLoginConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that the login never challenges an unauthenticated request.

        The landed authenticator is no entry point — it implements no entry
        point interface and starts nothing — so a request it does not answer
        is not redirected or challenged by it.
        """
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
        """Register the authenticator over the firewall's provider."""
        del builder
        settings = cast("JsonLoginConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'A JSON login on the firewall "{firewall_name}" needs a user provider; '
                f"name one on the firewall.",
            )

        options = {
            "check_path": settings.check_path,
            "username_path": settings.username_path,
            "password_path": settings.password_path,
        }

        def json_login_authenticator(
            http_utils: HttpUtils,
            provider: UserProviderInterface,
            responses: ResponseFactoryInterface,
            success_handler: object | None = None,
            failure_handler: object | None = None,
        ) -> JsonLoginAuthenticator:
            return JsonLoginAuthenticator(
                http_utils,
                provider,
                responses,
                cast("AuthenticationSuccessHandlerInterface | None", success_handler),
                cast("AuthenticationFailureHandlerInterface | None", failure_handler),
                options,
            )

        annotations: dict[str, object] = {
            "http_utils": HttpUtils,
            "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
            "responses": ResponseFactoryInterface,
        }
        if settings.success_handler is not None:
            annotations["success_handler"] = settings.success_handler
        if settings.failure_handler is not None:
            annotations["failure_handler"] = settings.failure_handler
        json_login_authenticator.__annotations__ = annotations
        json_login_authenticator.__name__ = f"json_login_authenticator_{firewall_name}"
        json_login_authenticator.__qualname__ = json_login_authenticator.__name__
        return (services.set(json_login_authenticator, qualifier=firewall_name).key,)
