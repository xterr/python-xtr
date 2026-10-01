"""What asks the voters and returns one decision."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .access_decision import AccessDecision

__all__ = ["AccessDecisionManagerInterface"]


@runtime_checkable
class AccessDecisionManagerInterface(Protocol):
    """Runs the voters for one attribute and reduces their votes with a strategy."""

    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Decide whether ``token`` may have the one attribute over ``subject``.

        Args:
            token: The token to decide for.
            attributes: Exactly one attribute; more is refused.
            subject: The subject the attribute concerns, or ``None``.
            access_decision: A record to fill; a fresh one when omitted, or the
                one already in progress when this call is nested inside a vote.

        Raises:
            InvalidArgumentError: When ``attributes`` does not hold exactly one.
        """
        ...
