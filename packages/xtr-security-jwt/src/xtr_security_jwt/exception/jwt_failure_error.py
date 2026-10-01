"""The base of the failure errors this library raises around a token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import SecurityError

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["JwtFailureError"]


class JwtFailureError(SecurityError):
    """A token could not be signed or verified, carrying a machine reason.

    The base of the encode and decode failures. It carries a ``reason`` — one
    of the reason constants its subclasses declare — and, when a token was read
    far enough to have one, the ``payload`` that was decoded. Deriving from the
    family's :class:`~xtr_security_core.exception.SecurityError` keeps one
    ``except SecurityError`` catching every error the family raises.

    Attributes:
        reason: The machine-readable cause, a subclass reason constant.
        payload: The claims decoded before the failure, when there were any.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        """Record the ``reason`` and the ``payload`` decoded before failing."""
        self.reason: str = reason
        self.payload: dict[str, object] | None = dict(payload) if payload is not None else None
        super().__init__(message)

    def get_reason(self) -> str:
        """Return the machine-readable cause of the failure."""
        return self.reason

    def get_payload(self) -> Mapping[str, object] | None:
        """Return the claims decoded before the failure, or ``None``."""
        return self.payload
