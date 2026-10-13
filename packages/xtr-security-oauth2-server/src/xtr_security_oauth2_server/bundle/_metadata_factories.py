"""Building what this server publishes about itself, and the endpoint serving it.

The document is made of the deployment's configuration, the grants its server
runs and nothing a request can change, so it is built once — when the endpoint
is first asked for, not when the container is built, because its absolute URLs
are built from an issuer only the deployment can supply.
"""

from __future__ import annotations

# The collected contributors and grants annotate the factory's parameters, and
# the container evaluates those annotations at runtime to decide what to inject.
from collections.abc import (
    Hashable,
    Mapping,
)
from typing import TYPE_CHECKING, Final

from xtr_dependency_injection import ServiceLocator, named_factory
from xtr_http_kernel.routing import RouterInterface
from xtr_security_oauth2_server_core.grant.abstract_authorize_grant import AbstractAuthorizeGrant
from xtr_security_oauth2_server_core.grant.device_code_grant import DeviceCodeGrant
from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface

from xtr_security_oauth2_server._endpoint_paths import METADATA_FIELDS
from xtr_security_oauth2_server.authorization_server_metadata import AuthorizationServerMetadata
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.routing import _endpoints

from ._required_settings import supplied, supplied_scopes

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_http_kernel.routing import RouteCollection

    from .oauth2_server_config import OAuth2ServerConfig

__all__ = ["metadata_controller_factory", "metadata_document"]

#: How a proof key may be derived. Both are published: the unhashed one is
#: accepted only from a client registered for it, which is a per-client matter
#: a discovery document cannot express.
_CODE_CHALLENGE_METHODS: Final = ("S256", "plain")

#: The endpoint each field of the description names. A route is found by the
#: function it calls, not by its name, so a routes file renaming the routes —
#: a name prefix, say — still has them published wherever they now are.
_FIELD_ENDPOINTS: Final[Mapping[str, object]] = {
    "authorization_endpoint": _endpoints.authorize,
    "token_endpoint": _endpoints.token,
    "jwks_uri": _endpoints.jwks,
    "revocation_endpoint": _endpoints.revoke,
    "introspection_endpoint": _endpoints.introspect,
    "device_authorization_endpoint": _endpoints.device_code,
}


def metadata_controller_factory(
    config: OAuth2ServerConfig,
) -> Callable[..., Awaitable[MetadataController]]:
    """Return a factory building the endpoint that describes this server.

    The grants are reached through a locator, by the qualifiers the grant pass
    enabled them on the server under, so none is built before the settings the
    document needs of its own are known to be there.
    """
    enabled = config.authorization_server.enable_metadata_endpoint

    async def oauth2_server_metadata_controller(
        contributors: Mapping[Hashable, MetadataContributorInterface],
        grants: ServiceLocator[GrantTypeInterface],
        router: RouterInterface,
        contributor_qualifiers: tuple[str, ...] = (),
        grant_qualifiers: tuple[str, ...] = (),
    ) -> MetadataController:
        return MetadataController(
            await metadata_document(
                config, grants, grant_qualifiers, router.get_route_collection()
            ),
            contributors,
            enabled,
            contributor_qualifiers,
        )

    oauth2_server_metadata_controller.__annotations__ = {
        "contributors": Mapping[Hashable, MetadataContributorInterface],
        "grants": ServiceLocator[GrantTypeInterface],
        "router": RouterInterface,
        "contributor_qualifiers": tuple[str, ...],
        "grant_qualifiers": tuple[str, ...],
        "return": MetadataController,
    }

    return named_factory(
        oauth2_server_metadata_controller,
        "oauth2_server_metadata_controller",
    )


async def metadata_document(
    config: OAuth2ServerConfig,
    grants: ServiceLocator[GrantTypeInterface],
    grant_qualifiers: tuple[str, ...],
    routes: RouteCollection,
) -> AuthorizationServerMetadata:
    """Return what this deployment publishes about itself.

    Only the endpoints actually served are named, because a client reads an
    absent field as "not supported": one turned off, and one the application's
    routes files left out. Each is published at the issuer and the path its
    route has in the application's table, so one a routes file moved is
    published where it now is. The flows are read off the grants the
    server runs rather than off the settings that turn the shipped ones on, so
    a flow an add-on or the application registered is named too, and the
    authorization endpoint is named whenever a grant answers there — the
    shipped one, or one an add-on put in its place.

    The issuer and the scopes are read before any grant is built, so a
    deployment missing either is told so by name rather than by whatever a
    grant needs first.

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
    scopes = supplied_scopes(config.scopes.available)
    running = [await grants.get(qualifier) for qualifier in grant_qualifiers]
    answers_authorization = any(isinstance(grant, AbstractAuthorizeGrant) for grant in running)
    issues_device_codes = any(isinstance(grant, DeviceCodeGrant) for grant in running)
    served = {
        "token_endpoint": True,
        "jwks_uri": True,
        "authorization_endpoint": answers_authorization,
        "revocation_endpoint": server.enable_revocation_endpoint,
        "introspection_endpoint": server.enable_introspection_endpoint,
        # Its endpoint answers only while the device flow is turned on.
        "device_authorization_endpoint": server.enable_device_code_grant and issues_device_codes,
    }
    paths = {route.endpoint: route.path for _name, route in reversed(list(routes))}
    endpoints: dict[str, str] = {}
    for field in METADATA_FIELDS:
        path = paths.get(_FIELD_ENDPOINTS[field]) if served[field] else None
        if path is not None:
            endpoints[field] = f"{issuer}{path}"

    return AuthorizationServerMetadata(
        issuer,
        endpoints,
        tuple(grant.get_identifier() for grant in running),
        scopes,
        _CODE_CHALLENGE_METHODS,
    )
