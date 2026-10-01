"""The failure raised when a token is missing a claim it must carry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .jwt_decode_failure_error import JwtDecodeFailureError
from .jwt_failure_error import JwtFailureError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["MissingClaimError"]


class MissingClaimError(JwtFailureError):
    """A token payload lacks a claim a caller required of it.

    Reported with the :data:`~JwtDecodeFailureError.INVALID_TOKEN` reason, so a
    caller reading the reason treats a missing claim as any other unreadable
    token, while ``claim`` names exactly which one was absent.

    Attributes:
        claim: The name of the required claim the payload did not carry.
    """

    def __init__(
        self,
        claim: str,
        *,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        """Record the required ``claim`` that was absent from the payload."""
        self.claim: str = claim
        super().__init__(
            JwtDecodeFailureError.INVALID_TOKEN,
            f'Missing required "{claim}" claim on JWT payload.',
            payload=payload,
        )
