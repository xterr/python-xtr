"""The caller is known, but not allowed to do this."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .security_error import SecurityError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authorization.access_decision import AccessDecision

__all__ = ["AccessDeniedError"]


class AccessDeniedError(SecurityError):
    """Authorization refused a known caller.

    Distinct from an authentication failure: who is calling was established;
    what they asked to do was not permitted. When the caller turns out not to
    be fully authenticated, an entry point may answer this with a challenge
    instead of a plain refusal; otherwise it becomes a 403.

    Attributes:
        attributes: The attributes that were checked (one, in this library).
        subject: The subject the attributes were checked against, if any.
        access_decision: The decision that refused, with its votes, if built.
    """

    attributes: tuple[object, ...]
    subject: object
    access_decision: AccessDecision | None

    def __init__(
        self,
        message: str = "Access Denied.",
        *,
        attributes: Sequence[object] = (),
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> None:
        """Record what was checked, against what, and the decision that refused."""
        self.attributes = tuple(attributes)
        self.subject = subject
        self.access_decision = access_decision
        super().__init__(message)
