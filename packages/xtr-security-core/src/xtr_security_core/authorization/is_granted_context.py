"""What a closure attribute is handed to decide access with."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from .access_decision_manager_interface import AccessDecisionManagerInterface

__all__ = ["IsGrantedContext"]


@dataclass(frozen=True, slots=True)
class IsGrantedContext:
    """The token, the user, and a way to ask further access questions.

    A closure attribute (see
    :class:`~xtr_security_core.authorization.voter.closure_voter.ClosureVoter`)
    receives one of these and the subject. It has the token and its user to
    reason about directly, and :meth:`is_granted` to defer to the ordinary
    machinery for a nested question — "may this token edit *this* book?" —
    which joins the decision already in progress rather than starting a new one.

    Attributes:
        token: The token the decision is being made for.
        user: The token's user, or ``None`` when nobody is authenticated.
    """

    token: TokenInterface = field(repr=False)
    user: UserInterface | None = field(repr=False)
    _manager: AccessDecisionManagerInterface

    async def is_granted(self, attribute: object, subject: object = None) -> bool:
        """Answer a nested access question for the same token.

        The question joins the decision in progress, so its votes are recorded
        alongside the outer one rather than in a decision of their own.
        """
        return await self._manager.decide(self.token, [attribute], subject)
