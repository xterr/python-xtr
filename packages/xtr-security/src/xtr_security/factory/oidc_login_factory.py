"""The factory that builds an OIDC authorization-code login for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_dependency_injection import Target
from xtr_event_dispatcher_contracts import (
    EventDispatcherInterface,
)
from xtr_security_core.user.user_provider_interface import (  # noqa: TC002 -- a factory signature the container reads
    UserProviderInterface,
)
from xtr_security_http import HttpUtils

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.oidc_configs import OidcLoginConfig
from xtr_security.exception import InvalidConfigurationError

from ._oidc_login_services import (
    oidc_token_refresh_listener_name,
    register_failure_handler,
    register_generator,
    register_refresh_listener,
    register_success_handler,
)
from ._oidc_provider_services import (
    register_client,
    register_discovery,
    register_id_token,
    register_refresher,
    register_verifier,
)
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
    from xtr_security_http.oidc import (
        OidcClientInterface,
        OidcDiscovery,
        OidcIdToken,
        OidcSignatureVerifier,
    )

__all__ = ["OidcLoginFactory", "oidc_token_refresh_listener_name"]


@final
class OidcLoginFactory(AuthenticatorFactoryInterface):
    """Builds the OIDC authorization-code login authenticator from configuration.

    The provider is discovered from the configured issuer — its endpoints read
    off the well-known document — and the client authenticates at its token
    endpoint by the configured method. The login answers on its check path
    with the default success and failure handlers, and a token-refresh listener
    joins the firewall's chain so a stored login renews its access token. A
    configured token generator registers under the firewall's own name, where
    the token-generate command finds it.

    The discovery, client, verifier, ID-token reader and refresher live in
    xtr-security-http's ``oidc`` extra (joserfc); this factory imports them
    only when it builds a login, so the bundle carries no JOSE dependency
    until an application configures one.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``oidc_login``."""
        return "oidc_login"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return 0

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`OidcLoginConfig`."""
        return OidcLoginConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that the login redirect is a real entry point."""
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
        """Register the provider services, the login and its refresh listener."""
        del builder
        settings = cast("OidcLoginConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'An OIDC login on the firewall "{firewall_name}" needs a user provider; '
                f"name one on the firewall.",
            )
        discovery_key = register_discovery(services, firewall_name, settings)
        id_token_key = register_id_token(services, firewall_name)
        verifier_key = register_verifier(services, firewall_name, settings, discovery_key)
        client_key = register_client(services, firewall_name, settings, discovery_key)
        refresher_key = register_refresher(
            services,
            firewall_name,
            settings,
            client_key,
            discovery_key,
            id_token_key,
            verifier_key,
        )
        register_refresh_listener(services, firewall_name, refresher_key)
        success_key = register_success_handler(services, firewall_name)
        failure_key = register_failure_handler(services, firewall_name)
        if settings.token_generator is not None:
            register_generator(services, firewall_name, settings.token_generator)
        return (
            _register_authenticator(
                services,
                firewall_name,
                settings,
                user_provider,
                client_key,
                discovery_key,
                id_token_key,
                verifier_key,
                success_key,
                failure_key,
            ),
        )


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression;
    the container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def _register_authenticator(  # noqa: PLR0913, PLR0917 -- one login from its firewall's parts
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    user_provider: ServiceKey,
    client_key: ServiceKey,
    discovery_key: ServiceKey,
    id_token_key: ServiceKey,
    verifier_key: ServiceKey | None,
    success_key: ServiceKey,
    failure_key: ServiceKey,
) -> ServiceKey:
    """Register the login authenticator over the provider services."""
    from xtr_security_http.authenticator.oidc_login_authenticator import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcLoginAuthenticator,
    )

    options = {
        "check_path": settings.check_path,
        "firewall_name": firewall_name,
        "scope": tuple(settings.scope.split()),
        "pkce_enabled": settings.pkce_enabled,
        "pkce_method": settings.pkce_method,
        "user_data_source": settings.user_data_source,
        "user_identifier_claim": settings.user_identifier_claim,
        "max_age": settings.max_age,
    }

    async def oidc_login_authenticator(  # noqa: PLR0913, PLR0917 -- the login's own wiring shape
        http_utils: HttpUtils,
        provider: UserProviderInterface,
        client: object,
        discovery: object,
        id_token: object,
        success: object,
        failure: object,
        clock: ClockInterface | None = None,
        verifier: object | None = None,
        dispatcher: EventDispatcherInterface | None = None,
    ) -> OidcLoginAuthenticator:
        return OidcLoginAuthenticator(
            http_utils,
            provider,
            cast("OidcClientInterface", client),
            cast("OidcDiscovery", discovery),
            cast("OidcIdToken", id_token),
            settings.client_id,
            cast("AuthenticationSuccessHandlerInterface", success),
            cast("AuthenticationFailureHandlerInterface", failure),
            options=options,
            authorization_params=dict(settings.authorization_params),
            signature_verifier=cast("OidcSignatureVerifier | None", verifier),
            clock=clock,
            event_dispatcher=dispatcher,
        )

    annotations: dict[str, object] = {
        "http_utils": HttpUtils,
        "provider": _qualified(user_provider),
        "client": _qualified(client_key),
        "discovery": _qualified(discovery_key),
        "id_token": _qualified(id_token_key),
        "success": _qualified(success_key),
        "failure": _qualified(failure_key),
        "clock": ClockInterface | None,
        "dispatcher": Annotated[
            EventDispatcherInterface, Target(firewall_dispatcher_name(firewall_name))
        ],
        "return": OidcLoginAuthenticator,
    }
    if verifier_key is not None:
        annotations["verifier"] = _qualified(verifier_key)
    oidc_login_authenticator.__annotations__ = annotations
    oidc_login_authenticator.__name__ = f"oidc_login_authenticator_{firewall_name}"
    oidc_login_authenticator.__qualname__ = oidc_login_authenticator.__name__
    return services.set(oidc_login_authenticator, qualifier=firewall_name).key
