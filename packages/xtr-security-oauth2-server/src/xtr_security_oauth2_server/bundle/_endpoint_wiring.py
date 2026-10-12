"""Registering the endpoints this package serves, and the one listener it ships."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_event_dispatcher.bundle import LISTENER_TAG

from xtr_security_oauth2_server.controller.device_code_controller import DeviceCodeController
from xtr_security_oauth2_server.controller.introspection_controller import (
    IntrospectionController,
)
from xtr_security_oauth2_server.controller.revocation_controller import RevocationController
from xtr_security_oauth2_server.controller.token_controller import TokenController
from xtr_security_oauth2_server.event_listener.add_client_default_scopes_listener import (
    AddClientDefaultScopesListener,
)
from xtr_security_oauth2_server.null_metadata_contributor import NullMetadataContributor
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from ._metadata_factories import metadata_controller_factory
from ._service_factories import authorization_controller_factory, jwks_controller_factory
from .metadata_pass import METADATA_TAG

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator

    from .oauth2_server_config import OAuth2ServerConfig

__all__ = ["register_controllers", "register_listeners"]


def register_controllers(
    config: OAuth2ServerConfig,
    services: ServiceConfigurator,
    log_channel: str | None,
) -> None:
    """Register one controller per endpoint, each knowing whether it is on.

    ``log_channel`` names the channel the authorization endpoint reports an
    unclaimed request on, or is ``None`` where this deployment logs nothing.
    """
    server = config.authorization_server
    # Scoped, unlike the rest: it reads the resource owner off the request
    # through the firewall's own per-request service, and a singleton cannot
    # hold something that changes with every request.
    _ = services.set(authorization_controller_factory(log_channel), lifetime="scoped")
    _ = services.set(TokenController)
    _ = services.set(DeviceCodeController).set_argument(
        "enabled",
        server.enable_device_code_grant,
    )
    _ = services.set(RevocationController).set_argument(
        "enabled",
        server.enable_revocation_endpoint,
    )
    _ = services.set(IntrospectionController).set_argument(
        "enabled",
        server.enable_introspection_endpoint,
    )
    _ = services.set(metadata_controller_factory(config))
    _ = services.set(jwks_controller_factory(server))
    # One contributor that adds nothing, so the collection is never empty.
    _ = services.set(NullMetadataContributor).add_tag(METADATA_TAG)


def register_listeners(config: OAuth2ServerConfig, services: ServiceConfigurator) -> None:
    """Register the one listener this package ships, with the scopes it hands out.

    A client registered naming no scope is given the deployment's defaults.
    Left empty — which it may be — the listener leaves such a client
    scope-less, and the protocol's own rule applies to it: a client with no
    scopes accepts whatever a request asks for.
    """
    _ = (
        services.set(AddClientDefaultScopesListener)
        .set_argument("default_scopes", config.scopes.default)
        .add_tag(LISTENER_TAG, event=OAuth2Events.PRE_SAVE_CLIENT)
    )
