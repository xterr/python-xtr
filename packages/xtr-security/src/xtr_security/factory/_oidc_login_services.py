"""The OIDC login's own services: the refresh listener, the handlers, the generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target
from xtr_security_core import (
    TokenStorageInterface,
)
from xtr_security_http import HttpUtils

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator, ServiceKey

    from xtr_security.bundle.oidc_configs import OidcTokenGeneratorConfig

__all__ = [
    "oidc_token_refresh_listener_name",
    "register_failure_handler",
    "register_generator",
    "register_refresh_listener",
    "register_success_handler",
]


def oidc_token_refresh_listener_name(firewall_name: str) -> str:
    """The qualifier of a firewall's OIDC token-refresh chain listener."""
    return f"{firewall_name}#oidc_token_refresh_listener"


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression;
    the container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def register_refresh_listener(
    services: ServiceConfigurator,
    firewall_name: str,
    refresher_key: ServiceKey,
) -> None:
    """Register the chain listener that renews a stored login's access token."""
    from xtr_security_http import (  # noqa: PLC0415 -- bare of the oidc extra
        FirewallListenerInterface,
        OidcTokenRefreshListener,
    )

    def oidc_token_refresh_listener(
        storage: TokenStorageInterface,
        refresher: object,
    ) -> OidcTokenRefreshListener:
        return OidcTokenRefreshListener(storage, cast("OidcTokenRefresher", refresher))

    oidc_token_refresh_listener.__annotations__ = {
        "storage": TokenStorageInterface,
        "refresher": _qualified(refresher_key),
        "return": OidcTokenRefreshListener,
    }
    oidc_token_refresh_listener.__name__ = f"oidc_token_refresh_listener_{firewall_name}"
    oidc_token_refresh_listener.__qualname__ = oidc_token_refresh_listener.__name__
    qualifier = oidc_token_refresh_listener_name(firewall_name)
    _ = services.set(oidc_token_refresh_listener, qualifier=qualifier, lifetime="scoped")
    services.alias(
        FirewallListenerInterface,
        OidcTokenRefreshListener,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )


def register_success_handler(services: ServiceConfigurator, firewall_name: str) -> ServiceKey:
    """Register the default success handler the login answers with."""
    from xtr_security_http import (  # noqa: PLC0415 -- bare of the oidc extra
        DefaultAuthenticationSuccessHandler,
    )

    def default_authentication_success_handler(
        http_utils: HttpUtils,
    ) -> DefaultAuthenticationSuccessHandler:
        return DefaultAuthenticationSuccessHandler(http_utils)

    default_authentication_success_handler.__annotations__ = {
        "http_utils": HttpUtils,
        "return": DefaultAuthenticationSuccessHandler,
    }
    default_authentication_success_handler.__name__ = f"oidc_success_handler_{firewall_name}"
    default_authentication_success_handler.__qualname__ = (
        default_authentication_success_handler.__name__
    )
    return services.set(
        default_authentication_success_handler, qualifier=f"{firewall_name}#oidc_success_handler"
    ).key


def register_failure_handler(services: ServiceConfigurator, firewall_name: str) -> ServiceKey:
    """Register the default failure handler the login answers with."""
    from xtr_security_http import (  # noqa: PLC0415 -- bare of the oidc extra
        DefaultAuthenticationFailureHandler,
    )

    def default_authentication_failure_handler(
        http_utils: HttpUtils,
    ) -> DefaultAuthenticationFailureHandler:
        return DefaultAuthenticationFailureHandler(http_utils, firewall_name=firewall_name)

    default_authentication_failure_handler.__annotations__ = {
        "http_utils": HttpUtils,
        "return": DefaultAuthenticationFailureHandler,
    }
    default_authentication_failure_handler.__name__ = f"oidc_failure_handler_{firewall_name}"
    default_authentication_failure_handler.__qualname__ = (
        default_authentication_failure_handler.__name__
    )
    return services.set(
        default_authentication_failure_handler, qualifier=f"{firewall_name}#oidc_failure_handler"
    ).key


def register_generator(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcTokenGeneratorConfig,
) -> None:
    """Register the token generator under the firewall's own name.

    The token-generate command collects every generator by that qualifier, so
    its ``--firewall`` option names the firewall whose keys the mint signs
    with.
    """
    from xtr_security_http.access_token.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcTokenGenerator,
    )

    def oidc_token_generator(clock: ClockInterface | None = None) -> OidcTokenGenerator:
        import json  # noqa: PLC0415 -- the standard library's reader, beside the gated import

        from joserfc.jwk import (  # noqa: PLC0415 -- guarded behind the oidc extra
            KeySet as JoserfcKeySet,
        )

        return OidcTokenGenerator(
            tuple(settings.algorithms),
            JoserfcKeySet.import_key_set(cast("KeySetSerialization", json.loads(settings.keyset))),
            settings.audience,
            tuple(settings.issuers),
            claim=settings.claim,
            clock=clock,
        )

    oidc_token_generator.__annotations__ = {
        "clock": ClockInterface | None,
        "return": OidcTokenGenerator,
    }
    oidc_token_generator.__name__ = f"oidc_token_generator_{firewall_name}"
    oidc_token_generator.__qualname__ = oidc_token_generator.__name__
    _ = services.set(oidc_token_generator, qualifier=firewall_name)


if TYPE_CHECKING:
    from joserfc._keys import KeySetSerialization
    from xtr_security_http.oidc import OidcTokenRefresher
