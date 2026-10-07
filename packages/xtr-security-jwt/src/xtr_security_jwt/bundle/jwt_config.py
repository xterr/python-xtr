"""The configuration the JWT bundle builds from."""

from __future__ import annotations

from collections.abc import (
    Sequence,  # noqa: TC003 -- a bundle config: its annotations are read at runtime
)
from dataclasses import dataclass, field

from xtr_security_core.exception import InvalidArgumentError

from .encoder_config import EncoderConfig
from .token_extractors_configs import TokenExtractorsConfig

__all__ = ["JwtConfig"]


@dataclass(frozen=True, slots=True)
class JwtConfig:
    """Everything the JWT bundle signs and verifies with, mirroring the reference options.

    Two fields a deployment must set are ``secret_key`` — the private key or
    shared secret that signs, given as the key text or the path of a file holding
    it — and ``issuer``, the name every minted token is stamped with and every
    presented token is checked against. The public key is derived from the signing
    key when absent; ``additional_public_keys`` name files of other keys tokens
    may also be verified against. The bundle fails the build with a clear error
    when ``secret_key`` or ``issuer`` is unset, so a misconfiguration is caught at
    build rather than at the first signature.

    Attributes:
        secret_key: The private key or shared secret that signs, as text or a
            file path. Required — the build fails without it.
        issuer: The ``iss`` every token is stamped with and checked against.
            Required — the build fails without it.
        audience: The audiences a token is minted for; when set, every token
            carries them as ``aud`` and a presented token must name at least one.
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
    issuer: str = ""
    audience: Sequence[str] = ()
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
        """Refuse a clock skew below zero, an empty user-id claim or a string audience.

        The absence of a signing key is not refused here — the zero-config path
        must build — but at the build, where the bundle names the missing setting.
        The issuer is likewise left to the build: an empty one is allowed on the
        config object, and the bundle refuses it there.

        Raises:
            InvalidArgumentError: When the clock skew is negative, the token
                lifetime is not positive, the user-id claim is empty, or the
                audience is a single string.
        """
        if self.clock_skew < 0:
            raise InvalidArgumentError("The clock skew cannot be negative.")
        if self.token_ttl <= 0:
            raise InvalidArgumentError("The token lifetime must be a positive number of seconds.")
        if not self.user_id_claim:
            raise InvalidArgumentError("The user-id claim cannot be empty.")
        if isinstance(self.audience, str):
            # A bare string is a sequence of its own letters, so ``aud`` "a"
            # would satisfy an audience of "api". One name is a one-name tuple.
            raise InvalidArgumentError(
                "The audience field is a sequence of audience names, not one name: a "
                f"bare string is read letter by letter. Write audience=({self.audience!r},).",
            )
