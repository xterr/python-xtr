"""What the authorization server signs, seals, issues and runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from urllib.parse import urlsplit

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

# The response type a deployment may put in place of the bearer document is
# named as a class the container builds, so this annotation is read at runtime.
from xtr_security_oauth2_server.response_types.response_type_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    ResponseTypeInterface,
)

__all__ = ["AuthorizationServerConfig"]

#: An hour: short enough that a token that escapes is of little use, long
#: enough that a client is not refreshing constantly.
DEFAULT_ACCESS_TOKEN_TTL = timedelta(hours=1)

#: Thirty days, as the reference server's one month.
DEFAULT_REFRESH_TOKEN_TTL = timedelta(days=30)

#: Ten minutes: an authorization code is redeemed by the client immediately
#: after the browser hands it over, so anything longer is only exposure.
DEFAULT_AUTH_CODE_TTL = timedelta(minutes=10)

#: Ten minutes, as the authorization code: long enough for somebody to walk to
#: another device and type a user code.
DEFAULT_DEVICE_CODE_TTL = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class AuthorizationServerConfig:
    """Everything the server issuing tokens is built from.

    Buildable with no arguments, because the bundle has to be declarable
    before any application configures it — but not *usable* that way: the
    build stops with
    :class:`~xtr_security_oauth2_server.exception.InvalidConfigurationError`
    naming each of ``private_key``, ``encryption_key`` and ``issuer`` that is
    still unset. There is no safe default for a signing key, for the key this
    server's own payloads are sealed with, or for the name every token claims
    to come from.

    Validation here is of shape, never of presence: an issuer that is not an
    origin, a lifetime that is not positive, a polling interval below zero.
    Presence is the bundle's to report, so that a deployment missing four
    settings is told all four at once.

    Attributes:
        private_key: The key access tokens are signed with, as PEM text or the
            path of a file holding it.
        private_key_passphrase: The pass phrase that key is encrypted with, or
            empty for none.
        encryption_key: A password, or the base64url of a key's bytes, that
            authorization codes and refresh tokens are sealed with.
        encryption_key_type: Which of the two ``encryption_key`` is.
        issuer: The origin this server is known by, claimed as ``iss`` by every
            token and published as the discovery document's ``issuer``. An
            origin and nothing more, because the document lives at a fixed path
            under it.
        audience: Who access tokens are addressed to, or ``None`` to address
            the client each was issued to.
        signature_algorithm: How an access token is signed.
        additional_public_keys: Files of further public keys tokens may also be
            verified against, so a key can be rotated without a flag day.
        access_token_ttl: How long an issued access token lasts.
        refresh_token_ttl: How long an issued refresh token lasts.
        auth_code_ttl: How long an issued authorization code lasts.
        device_code_ttl: How long an issued device code lasts.
        enable_client_credentials_grant: Whether a client may authenticate as
            itself.
        enable_refresh_token_grant: Whether a refresh token may be redeemed.
        enable_auth_code_grant: Whether the browser redirect flow runs.
        enable_password_grant: Whether a resource owner's own credentials are
            accepted. Off: the flow is withdrawn from the protocol, and it
            hands the password of a person to a client.
        enable_implicit_grant: Whether a token is handed straight to the
            browser. Off, for the same reason.
        enable_device_code_grant: Whether a device with no browser may poll for
            a token.
        require_code_challenge_for_public_clients: Whether a client holding no
            secret must prove possession of a code verifier.
        persist_access_token: Whether each issued access token is written down,
            which is what makes withdrawing one before it expires possible.
        revoke_refresh_tokens: Whether redeeming a refresh token withdraws it.
        response_type_class: The response type the token endpoint answers with,
            or ``None`` for the bearer document nearly every deployment hands
            out.
        device_code_verification_uri: Where a person is told to go to type the
            user code. Required when the device flow runs: the answer to a
            device names it, and a device shows it on a screen.
        enable_device_code_verification_uri_complete_generation: Whether the
            answer also carries the verification URI with the code already in
            it.
        device_code_polling_interval: How many seconds a device must wait
            between polls.
        enable_device_code_polling_interval_visibility: Whether that interval is
            told to the device.
        enable_revocation_endpoint: Whether a client may ask for a token to be
            withdrawn.
        enable_introspection_endpoint: Whether a client may ask what this server
            says about a token. Off by default: it answers questions about
            tokens issued to *other* clients, so a deployment turns it on
            deliberately.
        enable_metadata_endpoint: Whether this server describes itself.
    """

    private_key: str | None = None
    private_key_passphrase: str = ""
    encryption_key: str | None = None
    encryption_key_type: Literal["plain", "key"] = "plain"
    issuer: str | None = None
    audience: str | None = None
    signature_algorithm: str = "RS256"
    additional_public_keys: tuple[str, ...] = ()
    access_token_ttl: timedelta = DEFAULT_ACCESS_TOKEN_TTL
    refresh_token_ttl: timedelta = DEFAULT_REFRESH_TOKEN_TTL
    auth_code_ttl: timedelta = DEFAULT_AUTH_CODE_TTL
    device_code_ttl: timedelta = DEFAULT_DEVICE_CODE_TTL
    enable_client_credentials_grant: bool = True
    enable_refresh_token_grant: bool = True
    enable_auth_code_grant: bool = True
    enable_password_grant: bool = False
    enable_implicit_grant: bool = False
    enable_device_code_grant: bool = True
    require_code_challenge_for_public_clients: bool = True
    persist_access_token: bool = True
    revoke_refresh_tokens: bool = True
    response_type_class: type[ResponseTypeInterface] | None = None
    device_code_verification_uri: str = ""
    enable_device_code_verification_uri_complete_generation: bool = True
    device_code_polling_interval: int = 5
    enable_device_code_polling_interval_visibility: bool = True
    enable_revocation_endpoint: bool = True
    enable_introspection_endpoint: bool = False
    enable_metadata_endpoint: bool = True

    def __post_init__(self) -> None:
        """Refuse a setting that is present but cannot be used.

        Raises:
            InvalidConfigurationError: When the issuer is not an origin, when
                any lifetime is not positive, when the polling interval is
                negative, or when the signature algorithm is empty.
        """
        if self.issuer is not None:
            _refuse_unless_an_origin(self.issuer)
        for name, lifetime in (
            ("access_token_ttl", self.access_token_ttl),
            ("refresh_token_ttl", self.refresh_token_ttl),
            ("auth_code_ttl", self.auth_code_ttl),
            ("device_code_ttl", self.device_code_ttl),
        ):
            if lifetime <= timedelta(0):
                raise InvalidConfigurationError(
                    f"The lifetime authorization_server.{name} is {lifetime}; a credential "
                    "that has already expired when it is issued can never be used, so it "
                    "must be a positive length of time.",
                )
        if self.device_code_polling_interval < 0:
            raise InvalidConfigurationError(
                "The setting authorization_server.device_code_polling_interval is "
                f"{self.device_code_polling_interval}; a device cannot wait a negative "
                "number of seconds between polls.",
            )
        if not self.signature_algorithm:
            raise InvalidConfigurationError(
                "The setting authorization_server.signature_algorithm is empty; name the "
                "algorithm access tokens are signed with, such as 'RS256'.",
            )


def _refuse_unless_an_origin(issuer: str) -> None:
    """Refuse ``issuer`` unless it is a scheme and a host and nothing more.

    The discovery document lives at a fixed path under the issuer, so an issuer
    carrying a path of its own would put that document somewhere no client
    would look — and the ``iss`` every token claims has to be exactly this
    string.

    Raises:
        InvalidConfigurationError: When the issuer is not an origin.
    """
    split = urlsplit(issuer)
    if (
        split.scheme == ""
        or split.netloc == ""
        or split.path != ""
        or split.query != ""
        or split.fragment != ""
    ):
        raise InvalidConfigurationError(
            f"The setting authorization_server.issuer is {issuer!r}, which is not an origin; "
            "name it as a scheme and a host with no path, query or fragment, such as "
            "'https://authorization.example.com'.",
        )
