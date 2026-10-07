"""How a token is signed, as configuration."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
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
        """Refuse an algorithm this library will not sign with, or a bad encoder.

        Raises:
            InvalidArgumentError: When the algorithm is not supported, or the
                encoder override is not a class implementing
                :class:`JwtEncoderInterface` — an instance or a name written
                where the class belongs is named here rather than reaching
                ``issubclass``, which would raise a ``TypeError`` of its own.
        """
        _ = key_type_for_algorithm(self.signature_algorithm)
        if self.service is not None and not (
            # The annotation says class; an application writing a configuration
            # is not held to it, and this is where that is caught.
            isinstance(self.service, type)  # pyright: ignore[reportUnnecessaryIsInstance]
            and issubclass(self.service, JwtEncoderInterface)
        ):
            raise InvalidArgumentError(
                "The encoder service must be a class implementing JwtEncoderInterface.",
            )
