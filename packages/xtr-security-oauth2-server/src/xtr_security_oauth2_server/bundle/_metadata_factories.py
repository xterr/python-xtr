"""Building what this server publishes about itself, and the endpoint serving it.

The document is made of the deployment's configuration and nothing a request
can change, so it is built once — when the endpoint is first asked for, not
when the container is built, because its absolute URLs are built from an issuer
only the deployment can supply.
"""

from __future__ import annotations

# The collected contributors annotate the factory's parameters, and the
# container evaluates those annotations at runtime to decide what to inject.
from collections.abc import (
    Hashable,
    Mapping,
)
from typing import TYPE_CHECKING, Final

from xtr_dependency_injection import named_factory

from xtr_security_oauth2_server._endpoint_paths import METADATA_FIELDS
from xtr_security_oauth2_server.authorization_server_metadata import AuthorizationServerMetadata
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.oauth2_grants import OAuth2Grants

from ._required_settings import supplied, supplied_scopes

if TYPE_CHECKING:
    from collections.abc import Callable

    from .oauth2_server_config import OAuth2ServerConfig

__all__ = ["enabled_grants", "metadata_controller_factory", "metadata_document"]

#: How a proof key may be derived. Both are published: the unhashed one is
#: accepted only from a client registered for it, which is a per-client matter
#: a discovery document cannot express.
_CODE_CHALLENGE_METHODS: Final = ("S256", "plain")


def metadata_controller_factory(
    config: OAuth2ServerConfig,
) -> Callable[..., MetadataController]:
    """Return a factory building the endpoint that describes this server."""
    enabled = config.authorization_server.enable_metadata_endpoint

    def oauth2_server_metadata_controller(
        contributors: Mapping[Hashable, MetadataContributorInterface],
        contributor_qualifiers: tuple[str, ...] = (),
    ) -> MetadataController:
        return MetadataController(
            metadata_document(config),
            contributors,
            enabled,
            contributor_qualifiers,
        )

    oauth2_server_metadata_controller.__annotations__ = {
        "contributors": Mapping[Hashable, MetadataContributorInterface],
        "contributor_qualifiers": tuple[str, ...],
        "return": MetadataController,
    }

    return named_factory(
        oauth2_server_metadata_controller,
        "oauth2_server_metadata_controller",
    )


def metadata_document(config: OAuth2ServerConfig) -> AuthorizationServerMetadata:
    """Return what this deployment publishes about itself.

    Only the endpoints actually served are named, because a client reads an
    absent field as "not supported".

    Raises:
        InvalidConfigurationError: When the deployment named no issuer, so
            there is nothing to build the absolute URLs from, or no scope, so
            there would be nothing to publish as supported.
    """
    server = config.authorization_server
    issuer = supplied(
        server.issuer,
        "authorization_server.issuer",
        "this server could not say who it is, nor where its endpoints are",
    )
    served = {
        "token_endpoint": True,
        "jwks_uri": True,
        "authorization_endpoint": server.enable_auth_code_grant or server.enable_implicit_grant,
        "revocation_endpoint": server.enable_revocation_endpoint,
        "introspection_endpoint": server.enable_introspection_endpoint,
        "device_authorization_endpoint": server.enable_device_code_grant,
    }
    endpoints = {
        field: f"{issuer}{METADATA_FIELDS[field]}" for field, enabled in served.items() if enabled
    }

    return AuthorizationServerMetadata(
        issuer,
        endpoints,
        enabled_grants(config),
        supplied_scopes(config.scopes.available),
        _CODE_CHALLENGE_METHODS,
    )


def enabled_grants(config: OAuth2ServerConfig) -> tuple[str, ...]:
    """Return the names a request may ask for a flow by, for the flows that run."""
    server = config.authorization_server
    by_setting = (
        (server.enable_auth_code_grant, OAuth2Grants.AUTHORIZATION_CODE),
        (server.enable_client_credentials_grant, OAuth2Grants.CLIENT_CREDENTIALS),
        (server.enable_refresh_token_grant, OAuth2Grants.REFRESH_TOKEN),
        (server.enable_device_code_grant, OAuth2Grants.DEVICE_CODE),
        (server.enable_password_grant, OAuth2Grants.PASSWORD),
        (server.enable_implicit_grant, OAuth2Grants.IMPLICIT),
    )

    return tuple(name for enabled, name in by_setting if enabled)
