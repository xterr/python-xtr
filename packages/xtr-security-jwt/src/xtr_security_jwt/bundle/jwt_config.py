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

    Buildable with no arguments, and the bundle builds and boots on it: a token
    cannot be signed until ``secret_key`` — the private key or shared secret
    that signs, as the key text or the path of a file holding it — names a key,
    and the first attempt raises
    :class:`~xtr_security_jwt.exception.MissingKeyError` saying so. ``issuer``,
    the name every minted token is stamped with and every presented token is
    checked against, is the kernel's name unless set. The public key is derived
    from the signing key when absent; ``additional_public_keys`` name files of
    other keys tokens may also be verified against.

    Attributes:
        secret_key: The private key or shared secret that signs, as text or a
            file path; ``None`` until a deployment configures one.
        issuer: The ``iss`` every token is stamped with and checked against:
            the kernel's name (``%kernel.name%``) by default.
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
    issuer: str = "%kernel.name%"
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

        The absence of a signing key is not refused at all until a token needs
        one. An issuer resolving to nothing is refused where the token manager is
        built, since an ``env()`` placeholder has no value before then.

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
