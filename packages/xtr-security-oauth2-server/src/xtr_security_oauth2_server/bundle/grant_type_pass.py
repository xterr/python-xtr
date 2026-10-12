"""Collecting the grants a deployment runs, and the lifetime each issues for."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_oauth2_server.grant.grant_type_interface import GrantTypeInterface

from ._parameters import ACCESS_TOKEN_TTL_DEFAULT

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceKey

__all__ = ["GRANT_TAG", "GrantTypePass"]

#: The tag a grant carries to be run by this deployment's authorization server.
#: Every class that is nominally a grant is tagged automatically, so an
#: application registering one has nothing to write; a grant that carries the
#: tag already — because the bundle gave it one, with a lifetime — is not tagged
#: a second time.
GRANT_TAG: Final = "oauth2_server.authorization_server.grant"

#: The tag attribute naming how long the tokens that grant issues last.
_TTL_ATTRIBUTE: Final = "access_token_ttl"

#: What a qualifier for a collected grant is built from, so each tagged grant
#: is reachable under the grant interface without colliding with another.
_QUALIFIER = "oauth2_server_grant_{index}"

#: The settings a deployment turns a shipped grant on with, named when none is.
_ENABLE_OPTIONS: Final = (
    "enable_client_credentials_grant",
    "enable_auth_code_grant",
    "enable_refresh_token_grant",
    "enable_device_code_grant",
    "enable_password_grant",
    "enable_implicit_grant",
)


@final
class GrantTypePass(CompilerPassInterface):
    """Hands the authorization server every grant that was tagged, in order.

    A grant is a flow, and which flows a deployment runs is the whole of what
    makes one authorization server different from another. The shipped grants
    are tagged by the bundle, already carrying the lifetime their tokens last;
    one an application or an add-on registers is tagged automatically for being
    a grant at all. Either way it arrives here.

    The container holds no method calls and a definition's arguments hold
    values rather than references, so a grant cannot simply be handed to the
    server as it is built. Instead each tagged grant is aliased under the grant
    interface with a qualifier of its own, and the server is given the ordered
    list of those qualifiers with the lifetime each issues for — which its
    factory replays, enabling one grant after another in exactly this order.

    A deployment with no grant at all is refused rather than left with a server
    that answers ``unsupported_grant_type`` to everything: an authorization
    server that can issue nothing is a deployment mistake, not a
    configuration.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Alias every tagged grant and give the server the order to enable them in.

        Raises:
            InvalidConfigurationError: When no grant is tagged at all, or when
                a tag names a lifetime that is not a length of time.
        """
        tagged = builder.find_tagged_service_ids(GRANT_TAG)
        if not tagged:
            raise InvalidConfigurationError(
                "This deployment runs no OAuth 2.0 grant, so its authorization server could "
                "issue nothing. Turn one on with one of the authorization_server settings "
                f"{list(_ENABLE_OPTIONS)}, or register a grant of your own tagged "
                f"{GRANT_TAG!r}.",
            )
        if not builder.has_definition(AuthorizationServer):
            # Nothing to hand them to; the bundle reports the missing settings
            # that left the server unregistered.
            return
        default_ttl = builder.get_parameter(ACCESS_TOKEN_TTL_DEFAULT)
        enabled: list[tuple[str, timedelta]] = []
        for index, (key, tags) in enumerate(tagged.items()):
            qualifier = _QUALIFIER.format(index=index)
            builder.set_alias(
                GrantTypeInterface,
                key[0],
                alias_qualifier=qualifier,
                target_qualifier=key[1],
            )
            # One definition is enabled once however often it was tagged: a
            # grant is known by the name requests ask for it by, and enabling
            # it twice would only replace it with itself.
            enabled.append((qualifier, _ttl_of(tags[0], default_ttl, key)))
        _ = builder.get_definition(AuthorizationServer).set_argument("grants", tuple(enabled))
        builder.log(self, f"Enabled {len(enabled)} grant(s) on the authorization server.")


def _ttl_of(
    attributes: dict[str, object],
    default: object,
    key: ServiceKey,
) -> timedelta:
    """Return how long the grant ``key`` issues tokens for.

    Raises:
        InvalidConfigurationError: When the tag, or the fallback parameter,
            names something that is not a length of time.
    """
    named = attributes.get(_TTL_ATTRIBUTE, default)
    if not isinstance(named, timedelta):
        raise InvalidConfigurationError(
            f"The grant {key[0].__qualname__} is tagged with an {_TTL_ATTRIBUTE} of "
            f"{named!r}, which is not a length of time; tag it with a datetime.timedelta.",
        )

    return named
