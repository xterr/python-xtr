"""A generator whose values carry no character a URI would have to encode."""

from __future__ import annotations

import base64
import secrets
from typing import Final, final

from typing_extensions import override

from xtr_security_csrf.exception import InvalidArgumentError

from .token_generator_interface import TokenGeneratorInterface

__all__ = ["UriSafeTokenGenerator"]

# A value drawn from fewer than eight bits could be guessed.
_MINIMUM_ENTROPY: Final = 8


@final
class UriSafeTokenGenerator(TokenGeneratorInterface):
    """Mints URI-safe values: base64 with ``+``, ``/`` and ``=`` gone.

    A value that carries none of the characters a URI encodes sits in a
    query, a form field or a header as it is, without a reader having to
    decode anything first — which is why the padding is stripped too.
    """

    __slots__ = ("_entropy",)

    def __init__(self, entropy: int = 256) -> None:
        """Record how much entropy each minted value carries.

        Args:
            entropy: The bits of randomness each value is drawn from.

        Raises:
            InvalidArgumentError: When ``entropy`` is 7 bits or fewer — a
                value that short could be guessed.
        """
        if entropy < _MINIMUM_ENTROPY:
            raise InvalidArgumentError("The entropy should be greater than 7.")
        self._entropy = entropy

    @override
    def generate_token(self) -> str:
        """Return a fresh URI-safe value of the configured entropy."""
        raw = secrets.token_bytes(self._entropy // 8)
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
