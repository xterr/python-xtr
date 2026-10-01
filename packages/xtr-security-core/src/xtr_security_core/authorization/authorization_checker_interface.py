"""What answers "may the current caller do this?"."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .access_decision import AccessDecision

__all__ = ["AuthorizationCheckerInterface"]


@runtime_checkable
class AuthorizationCheckerInterface(Protocol):
    """Decides an attribute against the token of the current unit of work.

    The everyday way to ask an authorization question: it reads the current
    token from the storage — the anonymous token when none is set — and hands
    it, the attribute and the subject to the decision manager.
    """

    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Tell whether the current token may have ``attribute`` over ``subject``."""
        ...
