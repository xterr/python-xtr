"""A voter granting ``ORDER_VIEW`` to an order's owner — the owner-check the README's voter row.

A class implementing ``VoterInterface`` is gathered into the decision manager by the security
bundle's ``security.voter`` tag; ``@as_service`` registers it so the tag has a definition to
land on. It speaks only about ``ORDER_VIEW`` over an :class:`Order`, and grants when the token's
user is that order's owner — the ``email`` the order was placed under.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_core import Vote, Voter
from xtr_security_core.authentication.token.token_interface import TokenInterface

from .order import Order

__all__ = ["ORDER_VIEW", "OrderViewVoter"]

ORDER_VIEW = "ORDER_VIEW"


@final
@as_service
class OrderViewVoter(Voter):
    """Grants ``ORDER_VIEW`` over an order to the user who placed it."""

    @override
    def supports(self, attribute: object, subject: object) -> bool:
        """Speak only about ``ORDER_VIEW`` asked over an :class:`Order`."""
        return attribute == ORDER_VIEW and isinstance(subject, Order)

    @override
    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        """Grant when the token's user is the order's owner."""
        del attribute
        if not isinstance(subject, Order):
            return False
        owner = subject.email == token.get_user_identifier()
        if vote is not None and not owner:
            vote.add_reason("the order belongs to another customer")
        return owner
