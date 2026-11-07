"""Building the provider's services out of what the deployment configured.

A factory rather than a plain registration for each service built from
settings the container cannot hand over by itself: the claim sets the
application named, the algorithm the authorization server signs with, and the
identity provider the application may not have named yet.

Each factory is a closure over the settings it needs, returning the type it is
registered under, so the definition is keyed by that type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn

from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.entities.claim_set_entity import ClaimSetEntity
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
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
    "unset_identity_provider_factory",
]


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
) -> Callable[[], IdTokenSettings]:
    """Return a factory building what ID tokens are minted with.

    Args:
        algorithm: The algorithm the authorization server signs with, which
            its signer does not say.
        ttl: How long an ID token lasts, or ``None`` to have it expire with
            its access token.
    """

    def openid_connect_server_id_token_settings() -> IdTokenSettings:
        return IdTokenSettings(algorithm=algorithm, ttl=ttl)

    return openid_connect_server_id_token_settings


def unset_identity_provider_factory() -> Callable[[], IdentityProviderInterface]:
    """Return a factory standing in for the identity provider the deployment did not name.

    Registered so the provider builds and boots without one — the console
    still runs — while whatever first needs a user's claims is told which
    setting to write.
    """

    def openid_connect_server_identity_provider() -> IdentityProviderInterface:
        return _refuse_without_identity_provider()

    return openid_connect_server_identity_provider


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
