"""The configuration the JWT bundle builds from."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_security_core.exception import InvalidArgumentError

from .encoder_config import EncoderConfig
from .token_extractors_configs import TokenExtractorsConfig

__all__ = ["JwtConfig"]


@dataclass(frozen=True, slots=True)
class JwtConfig:
    """Everything the JWT bundle signs and verifies with, mirroring the reference options.

    The one field a deployment must set is ``secret_key`` — the private key or
    shared secret that signs, given as the key text or the path of a file holding
    it. The public key is derived from it when absent; ``additional_public_keys``
    name files of other keys tokens may also be verified against. The bundle
    fails the build with a clear error when no ``secret_key`` is configured, so a
    misconfiguration is caught at build rather than at the first signature.

    Attributes:
        secret_key: The private key or shared secret that signs, as text or a
            file path. Required — the build fails without it.
        public_key: The public key that verifies, or ``None`` to derive it.
        additional_public_keys: Files of extra public keys to also verify against.
        pass_phrase: The pass phrase the private key is encrypted with.
        token_ttl: How long a minted token lives, in seconds.
        allow_no_expiration: Whether a token without an expiry is honoured.
        clock_skew: Seconds of clock skew tolerated on a verified token's times.
        encoder: How a token is signed — the algorithm, and any encoder override.
        user_id_claim: The claim the user's identifier is written into and read
            back from.
        token_extractors: Where a firewall reads a token from.
    """

    secret_key: str | None = None
    public_key: str | None = None
    additional_public_keys: tuple[str, ...] = ()
    pass_phrase: str = ""
    token_ttl: int = 3600
    allow_no_expiration: bool = False
    clock_skew: int = 0
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    user_id_claim: str = "username"
    token_extractors: TokenExtractorsConfig = field(default_factory=TokenExtractorsConfig)

    def __post_init__(self) -> None:
        """Refuse a clock skew below zero or an empty user-id claim.

        The absence of a signing key is not refused here — the zero-config path
        must build — but at the build, where the bundle names the missing setting.

        Raises:
            InvalidArgumentError: When the clock skew is negative, the token
                lifetime is not positive, or the user-id claim is empty.
        """
        if self.clock_skew < 0:
            raise InvalidArgumentError("The clock skew cannot be negative.")
        if self.token_ttl <= 0:
            raise InvalidArgumentError("The token lifetime must be a positive number of seconds.")
        if not self.user_id_claim:
            raise InvalidArgumentError("The user-id claim cannot be empty.")
