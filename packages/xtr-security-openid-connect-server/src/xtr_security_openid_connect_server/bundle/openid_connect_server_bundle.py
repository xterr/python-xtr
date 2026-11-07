"""The bundle turning the OAuth 2.0 authorization server into an OpenID Connect provider."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, required_bundle
from xtr_security_http.firewall import FirewallListenerInterface
from xtr_security_oauth2_server.bundle import GRANT_TAG, METADATA_TAG, OAuth2ServerConfig

from xtr_security_openid_connect_server.controller.user_info_controller import UserInfoController
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_openid_connect_server.firewall.open_id_prompt_listener import (
    OpenIdPromptListener,
)
from xtr_security_openid_connect_server.grant.open_id_auth_code_grant import OpenIdAuthCodeGrant
from xtr_security_openid_connect_server.open_id_metadata_contributor import (
    OpenIdMetadataContributor,
)
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,
)
from xtr_security_openid_connect_server.response_types.id_token_response import IdTokenResponse

from ._service_factories import (
    claim_extractor_factory,
    id_token_settings_factory,
    open_id_prompt_listener,
    unset_identity_provider_factory,
)
from .openid_connect_server_config import OpenIdConnectServerConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_security_oauth2_server.bundle import AuthorizationServerConfig

__all__ = ["OpenIdConnectServerBundle"]

#: The scope a client asks for to sign the end-user in.
_OPENID_SCOPE: Final = "openid"

#: Where the authorization server's settings are written, and so overridden.
_SERVER_CONFIG_FILE: Final = "<app>/config/packages/oauth2_server.py"

#: What an application lists in its login firewall's ``listeners`` to have
#: ``prompt`` and ``max_age`` decided there.
_PROMPT_LISTENER: Final = "openid_connect_server#prompt_listener"


@final
@required_bundle("xtr_security_oauth2_server.bundle:OAuth2ServerBundle")
@required_bundle("xtr_security.bundle:SecurityBundle")
@required_bundle("xtr_clock.bundle:ClockBundle")
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle")
@required_bundle("xtr_http_kernel.bundle:HttpKernelBundle")
@as_bundle("openid_connect_server", config=OpenIdConnectServerConfig)
class OpenIdConnectServerBundle(Bundle[OpenIdConnectServerConfig]):
    """Turns this deployment's authorization server into an OpenID Connect provider.

    An identity layer exists only on top of a server that already issues
    access tokens, so listing this bundle brings the authorization server
    along, with the security family, the clock, the event dispatcher and the
    HTTP kernel that server is built on. The authorization server knows
    nothing of this bundle: this one plugs into it, through the settings it
    prepends and the flow it tags as a grant.

    Each peer is named by its ``"module:Class"`` string, the way the
    authorization server names its own: the kernel imports each one as it
    resolves the bundles, so a peer that is not installed is reported there,
    by name.

    It builds and boots with no configuration at all.
    """

    __slots__ = ()

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Put the sign-in's flow, answer and scope in place of the shipped ones."""
        builder.prepend_extension_config(OAuth2ServerConfig, _signing_in)

    @override
    def load_extension(
        self,
        config: OpenIdConnectServerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the claim sets, ID-token settings, identity provider, flow and endpoints.

        The token answer itself is not registered here: the authorization
        server registers whichever class its ``response_type_class`` names,
        which the prepend made this package's.

        The listener is a function, not a service: the dispatcher keeps a
        listener service once fetched, so it would have to be a singleton, and
        the security facade it reads is scoped to the request. A function's
        injected parameters are filled on every call instead.

        The userinfo controller is per-request for the same reason: it reads
        the token the request's firewall settled on. Its route resource is
        scanned so the HTTP kernel hands it to the application's routes files.

        The prompt step is per-request too, over the request's token storage,
        and is only registered: the application lists its qualifier in the
        login firewall's ``listeners``, since only it knows which firewall
        signs end-users in.
        """
        server = builder.get_extension_config(OAuth2ServerConfig).authorization_server
        _ = services.set(claim_extractor_factory(config.claim_sets))
        _ = services.set(id_token_settings_factory(server.signature_algorithm, config.id_token_ttl))
        if config.identity_provider is None:
            _ = services.set(unset_identity_provider_factory())
        else:
            # The application's class is built by the container, from its
            # constructor; the application does not register it itself.
            _ = services.set(config.identity_provider)
            services.alias(IdentityProviderInterface, config.identity_provider)
        # A tagged grant is handed none of the settings the authorization
        # server hands the grants it builds, so the three it applies to its own
        # redirect flow are read off its configuration and set here.
        _ = (
            services.set(OpenIdAuthCodeGrant)
            .set_argument("auth_code_ttl", server.auth_code_ttl)
            .set_argument("refresh_token_ttl", server.refresh_token_ttl)
            .set_argument(
                "require_code_challenge", server.require_code_challenge_for_public_clients
            )
            .add_tag(GRANT_TAG)
        )
        services.load("xtr_security_openid_connect_server.event_listener.auth_time_listener")
        _ = services.set(UserInfoController, lifetime="scoped")
        # Shared by every request, as the description endpoint it contributes
        # to is: it finds the userinfo endpoint's path in the application
        # being served each time it is read.
        _ = (
            services.set(OpenIdMetadataContributor)
            .set_argument("issuer", server.issuer)
            .set_argument("signature_algorithm", server.signature_algorithm)
            .add_tag(METADATA_TAG)
        )
        _ = (
            services.set(open_id_prompt_listener, qualifier=_PROMPT_LISTENER, lifetime="scoped")
            .set_argument("login_path", config.login_path)
            .set_argument("login_firewall", config.login_firewall)
            .set_argument("authorize_path", config.authorize_path)
        )
        services.alias(
            FirewallListenerInterface,
            OpenIdPromptListener,
            alias_qualifier=_PROMPT_LISTENER,
            target_qualifier=_PROMPT_LISTENER,
        )
        services.load("xtr_security_openid_connect_server.routing")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Refuse a deployment whose own configuration undid what this bundle prepended.

        Raises:
            InvalidConfigurationError: When the authorization server runs its
                shipped redirect flow, answers with something that cannot
                carry an ID token, or does not describe itself.
        """
        server = builder.get_extension_config(OAuth2ServerConfig).authorization_server
        refusals = _refusals(server)
        if refusals:
            raise InvalidConfigurationError(" ".join(refusals))


def _signing_in(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Return ``config`` with the sign-in's answer and scope, and the shipped flow off.

    The shipped redirect flow goes off because this package registers a flow
    answering the same name. ``openid`` joins the scopes only when the
    deployment named some: one that named none is told so by the authorization
    server, which it would not be if this package had named one for it.
    """
    available = config.scopes.available
    scopes = (
        replace(config.scopes, available=(*available, _OPENID_SCOPE))
        if available and _OPENID_SCOPE not in available
        else config.scopes
    )

    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            enable_auth_code_grant=False,
            response_type_class=IdTokenResponse,
        ),
        scopes=scopes,
    )


def _refusals(server: AuthorizationServerConfig) -> list[str]:
    """Return one sentence for each setting of ``server`` an ID token cannot be issued under."""
    overridden = (
        "This bundle sets it, and a @configure transform of the application's, which runs "
        f"after it, changed it back; remove that change from {_SERVER_CONFIG_FILE}."
    )
    refusals: list[str] = []
    if server.enable_auth_code_grant is not False:
        refusals.append(
            "The setting authorization_server.enable_auth_code_grant is True, so the shipped "
            "redirect flow would answer in place of the one that signs the end-user in. "
            f"{overridden}",
        )
    answer = server.response_type_class
    if answer is None or not issubclass(answer, IdTokenResponse):
        refusals.append(
            "The setting authorization_server.response_type_class names "
            f"{'no answer' if answer is None else answer.__name__}, which cannot carry an ID "
            f"token; it must be IdTokenResponse or a subclass of it. {overridden}",
        )
    if server.enable_metadata_endpoint is not True:
        refusals.append(
            "The setting authorization_server.enable_metadata_endpoint is False, so this "
            "server would not describe itself and no client could discover the OpenID "
            f"Connect provider; turn it back on in {_SERVER_CONFIG_FILE}.",
        )

    return refusals
