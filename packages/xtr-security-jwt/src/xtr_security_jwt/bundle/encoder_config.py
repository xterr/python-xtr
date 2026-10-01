"""How a token is signed, as configuration."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_security_jwt.services.key_loader._algorithms import key_type_for_algorithm

__all__ = ["EncoderConfig"]


@dataclass(frozen=True, slots=True)
class EncoderConfig:
    """The encoder a token is signed with, and the algorithm it signs with.

    Attributes:
        service: A registered encoder to sign with instead of the default, or
            ``None`` to sign with the joserfc encoder over the configured keys.
        signature_algorithm: The signature algorithm the default encoder uses.
    """

    service: type | None = None
    signature_algorithm: str = "RS256"

    def __post_init__(self) -> None:
        """Refuse an algorithm this library will not sign or verify with.

        Raises:
            InvalidArgumentError: When the algorithm is not supported.
        """
        _ = key_type_for_algorithm(self.signature_algorithm)
