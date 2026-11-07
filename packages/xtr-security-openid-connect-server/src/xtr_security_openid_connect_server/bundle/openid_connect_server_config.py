"""The configuration the OpenID Connect provider bundle builds from."""

from __future__ import annotations

# The kernel reads a bundle configuration's annotations at runtime, so none of
# these can hide under TYPE_CHECKING.
from collections.abc import Mapping  # noqa: TC003 -- read by the kernel at runtime
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final, final

from xtr_security_openid_connect_server.claim_extractor import ClaimExtractor
from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_openid_connect_server.repositories.identity_provider_interface import (
    IdentityProviderInterface,  # noqa: TC001 -- read by the kernel at runtime
)

__all__ = ["CONFIG_FILE", "OpenIdConnectServerConfig"]

#: Where an application writes this bundle's configuration.
CONFIG_FILE: Final = "<app>/config/packages/openid_connect_server.py"

_NO_TIME: Final = timedelta(0)


@final
@dataclass(frozen=True, slots=True)
class OpenIdConnectServerConfig:
    """Everything this deployment's OpenID Connect provider is configured with.

    Buildable with no arguments: the provider builds and boots on its
    defaults, and the one setting only the application can supply — where a
    signed-in user's claims come from — is reported where it is first needed,
    by the userinfo endpoint, never by the build.

    Attributes:
        identity_provider: The application's class that finds a signed-in user
            and their claims. The bundle registers it, so the container builds
            it from its constructor; the application does not register it
            itself.
        claim_sets: The claims each scope of the application's own reveals, by
            scope. The four scopes OpenID Connect Core defines come with
            theirs and cannot be given here.
        id_token_ttl: How long an ID token is good for, or ``None`` to have it
            expire with the access token issued beside it.
        login_path: Where an end-user asked to sign in again is sent.
        login_firewall: The firewall that signs an end-user in at
            ``login_path``, which remembers where to send them back.
        authorize_path: Where the authorization endpoint is served.
    """

    identity_provider: type[IdentityProviderInterface] | None = None
    claim_sets: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    id_token_ttl: timedelta | None = None
    login_path: str = "/login"
    login_firewall: str = "main"
    authorize_path: str = "/authorize"

    def __post_init__(self) -> None:
        """Refuse settings no provider could run with.

        Raises:
            InvalidConfigurationError: When a path or the firewall is named by
                an empty string, ``id_token_ttl`` is set and not positive, or
                ``claim_sets`` holds an empty scope or one the protocol
                defines.
        """
        for setting, value in (
            ("login_path", self.login_path),
            ("login_firewall", self.login_firewall),
            ("authorize_path", self.authorize_path),
        ):
            if value == "":
                raise InvalidConfigurationError(
                    f"The setting {setting} is empty; name it in {CONFIG_FILE}, or leave it "
                    "out for its default.",
                )
        if self.id_token_ttl is not None and self.id_token_ttl <= _NO_TIME:
            raise InvalidConfigurationError(
                f"The setting id_token_ttl is {self.id_token_ttl}, which would mint ID tokens "
                f"already expired; make it positive in {CONFIG_FILE}, or leave it out to have "
                "an ID token expire with its access token.",
            )
        protocol = ClaimExtractor()
        for scope in self.claim_sets:
            if scope == "":
                raise InvalidConfigurationError(
                    f"The setting claim_sets holds a claim set for an empty scope; name each "
                    f"scope in {CONFIG_FILE}.",
                )
            if protocol.has_claim_set(scope):
                raise InvalidConfigurationError(
                    f"The setting claim_sets holds a claim set for {scope!r}, a scope OpenID "
                    "Connect Core defines together with the claims it reveals; give these "
                    f"claims a scope of the application's own in {CONFIG_FILE}.",
                )
