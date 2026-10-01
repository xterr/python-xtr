"""What signs a set of claims into a token and reads one back."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["JwtEncoderInterface"]


@runtime_checkable
class JwtEncoderInterface(Protocol):
    """Signs a set of claims into a token and reads one back into claims.

    The low-level contract the token manager delegates to: it owns only the
    cryptography and the token's structure, deciding nothing about what the
    claims mean.
    """

    def encode(self, data: Mapping[str, object]) -> str:
        """Sign ``data`` into a compact token.

        Raises:
            JwtEncodeFailureError: When the token cannot be signed.
        """
        ...

    def decode(self, token: str) -> Mapping[str, object]:
        """Read ``token`` back into its claims.

        Raises:
            JwtDecodeFailureError: When the token cannot be read, has expired, or
                its signature does not verify.
        """
        ...
