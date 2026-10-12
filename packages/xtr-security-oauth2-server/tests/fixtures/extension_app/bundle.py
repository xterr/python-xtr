"""The bundle of an add-on built on this package's authorization server.

Everything an add-on does to a deployment, in one place: it prepends the two
settings that put its own answer and its own flow in place of the shipped ones,
registers the flow tagged as a grant — with a lifetime of its own — the answer
is built from, and tags what it contributes to this server's description.

It requires this package's bundle and this package's bundle knows nothing of
it: an add-on reaches in through the extension points, never the other way
round.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from xtr_security_oauth2_server.bundle import (
    GRANT_TAG,
    METADATA_TAG,
    OAuth2ServerBundle,
    OAuth2ServerConfig,
)

from .contributor import NonceMetadataContributor
from .grant import NonceAuthCodeGrant
from .response_type import NonceTokenResponse
from .stamp import NonceStamp

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["OWN_ACCESS_TOKEN_TTL", "ExtensionBundle"]

#: How long the tokens the add-on's flow issues last. Not the deployment's own
#: ``authorization_server.access_token_ttl``: a flow that hands out something
#: more than a bearer token may have a shorter one to justify, and the tag is
#: where it says so.
OWN_ACCESS_TOKEN_TTL: Final[timedelta] = timedelta(minutes=3)


@final
@required_bundle(OAuth2ServerBundle)
@as_bundle("nonce_extension")
class ExtensionBundle(Bundle):
    """Puts the add-on's flow, answer and contribution into this deployment."""

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Turn the shipped redirect flow off, and name the answer the add-on hands out."""
        builder.prepend_extension_config(OAuth2ServerConfig, _extended)

    @override
    def load_extension(
        self,
        config: object,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the flow, the service its answer is built from, and the contribution.

        A tagged grant is handed none of the settings the bundle hands a
        shipped one, so the lifetimes and the proof-key requirement are read
        off the deployment's own configuration here and set on the definition.
        """
        del config
        server = builder.get_extension_config(OAuth2ServerConfig).authorization_server
        _ = services.set(NonceStamp)
        _ = (
            services.set(NonceAuthCodeGrant)
            .set_argument("auth_code_ttl", server.auth_code_ttl)
            .set_argument("refresh_token_ttl", server.refresh_token_ttl)
            .set_argument(
                "require_code_challenge",
                server.require_code_challenge_for_public_clients,
            )
            .add_tag(GRANT_TAG, access_token_ttl=OWN_ACCESS_TOKEN_TTL)
        )
        _ = services.set(NonceMetadataContributor).add_tag(METADATA_TAG)


def _extended(config: OAuth2ServerConfig) -> OAuth2ServerConfig:
    """Return ``config`` with the add-on's answer in place of the bearer one.

    The shipped redirect flow goes off in the same breath: the add-on registers
    a flow answering the same name, and one name means one flow — a deployment
    left with both is refused while it is being assembled.
    """
    return replace(
        config,
        authorization_server=replace(
            config.authorization_server,
            enable_auth_code_grant=False,
            response_type_class=NonceTokenResponse,
        ),
    )
