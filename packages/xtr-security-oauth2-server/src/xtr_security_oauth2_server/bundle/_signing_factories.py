"""Building the keys this server signs its access tokens with.

The key loader and the JWS provider are registered under a qualifier of this
package's own rather than under the bare interfaces. The self-issued-token
package owns those: a deployment commonly runs both bundles — one firewall
signs in the end user, this server signs access tokens — and each has to keep
its own key. Nothing here is ever aliased to the unqualified names.

The key itself is read here rather than when the container is built: an
application with no key yet still gets a container, and so a console that can
mint one. Asking for anything that signs is what reports the key is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final

from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader import RawKeyLoader, signing_key_id
from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

from xtr_security_oauth2_server.entities.access_token_signer import AccessTokenSigner

from ._required_settings import supplied

if TYPE_CHECKING:
    from collections.abc import Callable

    from .authorization_server_config import AuthorizationServerConfig
    from .resource_server_config import ResourceServerConfig

__all__ = [
    "QUALIFIER",
    "jws_provider_factory",
    "key_loader_factory",
    "signer_factory",
]

#: What this package's own key loader and JWS provider are registered under.
QUALIFIER: Final = "oauth2_server"

#: An access token stamps its own expiry, so the provider is given no lifetime
#: of its own to impose on one.
_NO_TTL: Final = None

#: The clock skew a signature check tolerates. None here: the resource-server
#: side has its own leeway setting, and widening the window in two places would
#: make the real tolerance the sum of them.
_NO_CLOCK_SKEW: Final = 0


def key_loader_factory(
    authorization_server: AuthorizationServerConfig,
    resource_server: ResourceServerConfig,
) -> Callable[..., RawKeyLoader]:
    """Return a factory building this server's own key loader.

    The verifying key is the public half of the signing key unless a deployment
    named one, which is what a resource server running apart from the
    authorization server does: it holds the public half and never the private
    one.
    """
    signing_key = authorization_server.private_key
    passphrase = authorization_server.private_key_passphrase
    public_key = resource_server.public_key
    additional = authorization_server.additional_public_keys

    def oauth2_server_key_loader() -> RawKeyLoader:
        return RawKeyLoader(
            supplied(
                signing_key,
                "authorization_server.private_key",
                "this server has nothing to sign an access token with",
                "Mint one with 'oauth2-server:generate-keypair'.",
            ),
            public_key,
            passphrase or None,
            additional,
        )

    return named_factory(oauth2_server_key_loader, "oauth2_server_key_loader")


def jws_provider_factory(
    config: AuthorizationServerConfig,
) -> Callable[..., JoserfcJwsProvider]:
    """Return a factory building what signs an access token and checks one.

    No lifetime is imposed by the provider: each grant stamps the expiry its
    own tokens carry, so a second lifetime here would silently shorten or
    extend them.
    """
    algorithm = config.signature_algorithm

    def oauth2_server_jws_provider(
        key_loader: KeyLoaderInterface,
        clock: ClockInterface,
    ) -> JoserfcJwsProvider:
        return JoserfcJwsProvider(key_loader, algorithm, _NO_TTL, _NO_CLOCK_SKEW, clock)

    oauth2_server_jws_provider.__annotations__ = {
        "key_loader": Annotated[KeyLoaderInterface, Target(QUALIFIER)],
        "clock": ClockInterface,
        "return": JoserfcJwsProvider,
    }

    return named_factory(oauth2_server_jws_provider, "oauth2_server_jws_provider")


def signer_factory(config: AuthorizationServerConfig) -> Callable[..., AccessTokenSigner]:
    """Return a factory gathering everything an access token signs itself with.

    The key's published id is read from the key material itself rather than
    configured, so what a token's header names and what the published key set
    holds cannot drift apart.
    """
    issuer = config.issuer
    audience = config.audience
    algorithm = config.signature_algorithm

    def oauth2_server_access_token_signer(
        jws_provider: JoserfcJwsProvider,
        key_loader: KeyLoaderInterface,
        clock: ClockInterface,
    ) -> AccessTokenSigner:
        return AccessTokenSigner(
            jws_provider,
            signing_key_id(key_loader, algorithm),
            supplied(
                issuer,
                "authorization_server.issuer",
                "an access token would not say who issued it",
            ),
            clock,
            audience,
        )

    oauth2_server_access_token_signer.__annotations__ = {
        "jws_provider": Annotated[JoserfcJwsProvider, Target(QUALIFIER)],
        "key_loader": Annotated[KeyLoaderInterface, Target(QUALIFIER)],
        "clock": ClockInterface,
        "return": AccessTokenSigner,
    }

    return named_factory(
        oauth2_server_access_token_signer,
        "oauth2_server_access_token_signer",
    )
