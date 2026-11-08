"""Building the provider's services out of what the deployment configured.

A factory rather than a plain registration for each service built from
settings the container cannot hand over by itself: the claim sets the
application named, the algorithm the authorization server signs with (and,
for ``EdDSA``, the curve of its key), and the identity provider the
application may not have named yet. Each of those is a closure over the
settings it needs, returning the type it is registered under, so the
definition is keyed by that type.

The prompt step has a plain factory instead, its settings set on the
definition: its clock is optional to the class, which the container would
leave out, so the factory names it as a dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, NoReturn

# Read at runtime: the container evaluates the prompt step factory's
# annotations to know what to inject.
from xtr_clock import ClockInterface  # noqa: TC002 -- read by the container at runtime
from xtr_dependency_injection import Target
from xtr_http_kernel.bridge import (
    StarletteHttpFactoryInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_http.http_utils import (
    HttpUtils,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_jwt.services.key_loader import KeyLoaderInterface, public_key_set
from xtr_security_oauth2_server_core.authorization_server import (
    AuthorizationServer,  # noqa: TC002 -- read by the container at runtime
)

from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.entities.claim_set_entity import ClaimSetEntity
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_openid_connect_server.firewall.open_id_prompt_listener import (
    OpenIdPromptListener,
)
from xtr_security_openid_connect_server.id_token_settings import IdTokenSettings

# Read at runtime: the container keys an unset provider's factory by this
# return annotation.
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,  # noqa: TC001 -- read by the container at runtime
)

from .openid_connect_server_config import CONFIG_FILE

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import timedelta

__all__ = [
    "claim_extractor_factory",
    "id_token_settings_factory",
    "open_id_prompt_listener",
    "unset_identity_provider_factory",
]

#: The one signature algorithm whose name says no digest: the curve of its key does.
_EDWARDS_ALGORITHM: Final = "EdDSA"

#: What the authorization server registers its own key loader under: that
#: server's ``SERVICE_QUALIFIER``, spelled out rather than imported, because the
#: constant lives in a private module of that package, which publishes only the
#: string itself — ``Target("oauth2_server")`` is how it says to ask for its keys.
_AUTHORIZATION_SERVER_QUALIFIER: Final = "oauth2_server"


def claim_extractor_factory(
    claim_sets: Mapping[str, tuple[str, ...]],
) -> Callable[[], ClaimExtractor]:
    """Return a factory building the extractor holding the deployment's claim sets too."""
    entities = tuple(ClaimSetEntity(scope, names) for scope, names in claim_sets.items())

    def openid_connect_server_claim_extractor() -> ClaimExtractor:
        return ClaimExtractor(entities)

    return openid_connect_server_claim_extractor


def id_token_settings_factory(
    algorithm: str,
    ttl: timedelta | None,
) -> Callable[..., IdTokenSettings]:
    """Return a factory building what ID tokens are minted with.

    An ``EdDSA`` key may be on either Edwards curve, and an ``at_hash`` is
    hashed differently over each, so for that algorithm the curve is read off
    the authorization server's own key — the one an ID token is signed with —
    when the settings are first built, never while the container is. The key
    loader is that server's own: a deployment with no key yet still builds,
    and that server names the setting to write when the key is first needed.

    Args:
        algorithm: The algorithm the authorization server signs with, which
            its signer does not say.
        ttl: How long an ID token lasts, or ``None`` to have it expire with
            its access token.
    """

    def openid_connect_server_id_token_settings(key_loader: KeyLoaderInterface) -> IdTokenSettings:
        curve = _signing_curve(key_loader) if algorithm == _EDWARDS_ALGORITHM else None
        return IdTokenSettings(algorithm=algorithm, ttl=ttl, curve=curve)

    openid_connect_server_id_token_settings.__annotations__ = {
        "key_loader": Annotated[KeyLoaderInterface, Target(_AUTHORIZATION_SERVER_QUALIFIER)],
        "return": IdTokenSettings,
    }

    return openid_connect_server_id_token_settings


def _signing_curve(key_loader: KeyLoaderInterface) -> str | None:
    """Return the curve the authorization server's ``EdDSA`` key is on.

    Read off the key set that server publishes, whose first key is its
    signing key's public half: the ``crv`` there is the one a client reads to
    check the ``at_hash``, so the two cannot hash differently.
    """
    curve = public_key_set(key_loader, _EDWARDS_ALGORITHM)["keys"][0].get("crv")
    return curve if isinstance(curve, str) else None


def unset_identity_provider_factory() -> Callable[[], IdentityProviderInterface]:
    """Return a factory standing in for the identity provider the deployment did not name.

    Registered so the provider builds and boots without one — the console
    still runs — while whatever first needs a user's claims is told which
    setting to write.
    """

    def openid_connect_server_identity_provider() -> IdentityProviderInterface:
        return _refuse_without_identity_provider()

    return openid_connect_server_identity_provider


def open_id_prompt_listener(  # noqa: PLR0913, PLR0917 -- the container fills the step's parts by name
    token_storage: TokenStorageInterface,
    authorization_server: AuthorizationServer,
    http_utils: HttpUtils,
    response_factory: ResponseFactoryInterface,
    bridge: StarletteHttpFactoryInterface,
    clock: ClockInterface,
    *,
    login_path: str,
    login_firewall: str,
    authorize_path: str,
) -> OpenIdPromptListener:
    """Build the prompt step, timing sign-ins against the application's clock.

    The three settings are the bundle's to set on the definition.
    """
    return OpenIdPromptListener(
        token_storage,
        authorization_server,
        http_utils,
        response_factory,
        bridge,
        login_path=login_path,
        login_firewall=login_firewall,
        authorize_path=authorize_path,
        clock=clock,
    )


def _refuse_without_identity_provider() -> NoReturn:
    """Refuse to find a signed-in user's claims with no identity provider named.

    Raises:
        InvalidConfigurationError: Always.
    """
    raise InvalidConfigurationError(
        "The setting identity_provider is not configured, so there is nowhere to find a "
        f"signed-in user's claims. Name the application's class implementing "
        f"IdentityProviderInterface in {CONFIG_FILE}; the bundle registers it.",
    )
