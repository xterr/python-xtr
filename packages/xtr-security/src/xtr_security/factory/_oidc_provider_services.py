"""The OIDC provider services a login wires: discovery, client, tokens, refresher."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated, assert_never, cast

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator, ServiceKey

    from xtr_security.bundle.oidc_configs import OidcLoginConfig

__all__ = [
    "register_client",
    "register_discovery",
    "register_id_token",
    "register_refresher",
    "register_verifier",
]

_DISCOVERY_TIMEOUT = 10.0
"""Seconds a discovery fetch may take before it is abandoned — the same budget
the OIDC token handler's provider gives its own fetches: discovery runs once
per issuer, off the request path, so a budget above the general-purpose one
avoids a spurious failure on first use.
"""

_DISCOVERY_MAX_CONNECTIONS = 10
"""The ceiling on connections one provider's HTTP client keeps open."""


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression;
    the container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def _provider_http_client() -> object:
    """Build the HTTP client every provider fetch runs through."""
    from xtr_http_client import HttpxHttpClient  # noqa: PLC0415 -- guarded behind the oidc extra

    return HttpxHttpClient(
        {"timeout": _DISCOVERY_TIMEOUT},
        max_host_connections=_DISCOVERY_MAX_CONNECTIONS,
    )


def register_discovery(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
) -> ServiceKey:
    """Register the provider's discovery reader, keyed by the issuer."""
    from xtr_security_http.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcDiscovery,
    )

    def oidc_discovery() -> OidcDiscovery:
        from xtr_cache import ArrayAdapter  # noqa: PLC0415 -- guarded behind the oidc extra

        return OidcDiscovery(
            cast("HttpClientInterface", _provider_http_client()),
            ArrayAdapter(),
            issuer=settings.issuer,
        )

    oidc_discovery.__annotations__ = {"return": OidcDiscovery}
    oidc_discovery.__name__ = f"oidc_discovery_{firewall_name}"
    oidc_discovery.__qualname__ = oidc_discovery.__name__
    return services.set(oidc_discovery, qualifier=f"{firewall_name}#oidc_discovery").key


def register_id_token(services: ServiceConfigurator, firewall_name: str) -> ServiceKey:
    """Register the ID-token reader, over the application's clock."""
    from xtr_security_http.oidc import OidcIdToken  # noqa: PLC0415 -- guarded behind the oidc extra

    def oidc_id_token(clock: ClockInterface | None = None) -> OidcIdToken:
        return OidcIdToken(clock=clock)

    oidc_id_token.__annotations__ = {"clock": ClockInterface | None, "return": OidcIdToken}
    oidc_id_token.__name__ = f"oidc_id_token_{firewall_name}"
    oidc_id_token.__qualname__ = oidc_id_token.__name__
    return services.set(oidc_id_token, qualifier=f"{firewall_name}#oidc_id_token").key


def register_verifier(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    discovery_key: ServiceKey,
) -> ServiceKey | None:
    """Register the ID-token signature verifier, when algorithms name any."""
    if settings.signature_verifier_algorithms is None:
        return None
    from xtr_security_http.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcSignatureVerifier,
    )

    def oidc_signature_verifier(
        discovery: object,
        clock: ClockInterface | None = None,
    ) -> OidcSignatureVerifier:
        from xtr_cache import ArrayAdapter  # noqa: PLC0415 -- guarded behind the oidc extra

        return OidcSignatureVerifier(
            cast("OidcDiscovery", discovery),
            ArrayAdapter(),
            cast("HttpClientInterface", _provider_http_client()),
            algorithms=tuple(settings.signature_verifier_algorithms or ()),
            clock=clock,
        )

    oidc_signature_verifier.__annotations__ = {
        "discovery": _qualified(discovery_key),
        "clock": ClockInterface | None,
        "return": OidcSignatureVerifier,
    }
    oidc_signature_verifier.__name__ = f"oidc_signature_verifier_{firewall_name}"
    oidc_signature_verifier.__qualname__ = oidc_signature_verifier.__name__
    return services.set(
        oidc_signature_verifier, qualifier=f"{firewall_name}#oidc_signature_verifier"
    ).key


async def _client_authentication(  # noqa: PLR0911 -- one branch per authentication method
    settings: OidcLoginConfig,
    discovery: object,
    clock: ClockInterface | None,
) -> object:
    """Build how the client authenticates at the provider's token endpoint.

    The assertion methods sign their assertion for the issuer the discovery
    announces, read where they run so a redirecting provider cannot slip
    another one past them.
    """
    from xtr_security_http.oauth2.client_authentication import (  # noqa: PLC0415 -- the ungated trio
        ClientSecretBasic,
        ClientSecretPost,
        NoClientAuthentication,
    )

    reader = cast("OidcDiscovery", discovery)
    match settings.token_endpoint_auth_method:
        case "none":
            return NoClientAuthentication()
        case "client_secret_basic":
            return ClientSecretBasic(cast("str", settings.client_secret))
        case "client_secret_post":
            return ClientSecretPost(cast("str", settings.client_secret))
        case "client_secret_jwt":
            from xtr_security_http.oauth2.client_authentication.client_secret_jwt import (  # noqa: PLC0415 -- guarded behind the oidc extra
                ClientSecretJwt,
            )

            return ClientSecretJwt(
                cast("str", settings.client_secret),
                clock=clock,
                issuer=await reader.get_issuer(),
            )
        case "private_key_jwt":
            from joserfc.jwk import (  # noqa: PLC0415 -- guarded behind the oidc extra
                KeySet as JoserfcKeySet,
            )
            from xtr_security_http.oauth2.client_authentication.private_key_jwt import (  # noqa: PLC0415 -- guarded behind the oidc extra
                PrivateKeyJwt,
            )

            keys = JoserfcKeySet.import_key_set(
                cast(
                    "KeySetSerialization",
                    json.loads(cast("str", settings.client_authentication_keyset)),
                )
            )
            return PrivateKeyJwt(
                keys.keys[0],
                clock=clock,
                issuer=await reader.get_issuer(),
            )
        case "tls_client_auth":
            from xtr_security_http.oauth2.client_authentication.tls_client_auth import (  # noqa: PLC0415 -- the certificate rides the client
                TlsClientAuth,
            )

            return TlsClientAuth()
        case "self_signed_tls_client_auth":
            from xtr_security_http.oauth2.client_authentication.self_signed_tls_client_auth import (  # noqa: PLC0415 -- the certificate rides the client
                SelfSignedTlsClientAuth,
            )

            return SelfSignedTlsClientAuth()
        case _:  # pragma: no cover -- exhaustive over TokenEndpointAuthMethod
            assert_never(settings.token_endpoint_auth_method)


def register_client(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    discovery_key: ServiceKey,
) -> ServiceKey:
    """Register the OIDC client the login exchanges its code through."""
    from xtr_security_http.oidc import OidcClient  # noqa: PLC0415 -- guarded behind the oidc extra

    async def oidc_client(
        discovery: object,
        clock: ClockInterface | None = None,
    ) -> OidcClient:
        return OidcClient(
            cast("HttpClientInterface", _provider_http_client()),
            cast("OidcDiscovery", discovery),
            settings.client_id,
            cast(
                "ClientAuthenticationInterface",
                await _client_authentication(settings, discovery, clock),
            ),
            certificate_options=(
                dict(settings.certificate_options)
                if settings.certificate_options is not None
                else None
            ),
        )

    oidc_client.__annotations__ = {
        "discovery": _qualified(discovery_key),
        "clock": ClockInterface | None,
        "return": OidcClient,
    }
    oidc_client.__name__ = f"oidc_client_{firewall_name}"
    oidc_client.__qualname__ = oidc_client.__name__
    return services.set(oidc_client, qualifier=f"{firewall_name}#oidc_client").key


def register_refresher(  # noqa: PLR0913, PLR0917 -- one refresher from its firewall's parts
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    client_key: ServiceKey,
    discovery_key: ServiceKey,
    id_token_key: ServiceKey,
    verifier_key: ServiceKey | None,
) -> ServiceKey:
    """Register the refresher that renews a stored login's access token."""
    from xtr_security_http.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcTokenRefresher,
    )

    def oidc_token_refresher(
        client: object,
        discovery: object,
        id_token: object,
        clock: ClockInterface | None = None,
        verifier: object | None = None,
    ) -> OidcTokenRefresher:
        return OidcTokenRefresher(
            cast("OidcClientInterface", client),
            cast("OidcDiscovery", discovery),
            cast("OidcIdToken", id_token),
            settings.client_id,
            signature_verifier=cast("OidcSignatureVerifier | None", verifier),
            clock=clock,
        )

    oidc_token_refresher.__annotations__ = {
        "client": _qualified(client_key),
        "discovery": _qualified(discovery_key),
        "id_token": _qualified(id_token_key),
        "clock": ClockInterface | None,
        "return": OidcTokenRefresher,
    }
    if verifier_key is not None:
        oidc_token_refresher.__annotations__["verifier"] = _qualified(verifier_key)
    oidc_token_refresher.__name__ = f"oidc_token_refresher_{firewall_name}"
    oidc_token_refresher.__qualname__ = oidc_token_refresher.__name__
    return services.set(oidc_token_refresher, qualifier=f"{firewall_name}#oidc_token_refresher").key


if TYPE_CHECKING:
    from joserfc._keys import KeySetSerialization
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_security_http.oauth2.client_authentication import (
        ClientAuthenticationInterface,
    )
    from xtr_security_http.oidc import (
        OidcClientInterface,
        OidcDiscovery,
        OidcIdToken,
        OidcSignatureVerifier,
    )
