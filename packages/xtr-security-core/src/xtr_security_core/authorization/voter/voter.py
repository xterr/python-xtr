"""The template every simple voter fills in."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from .access import Access
from .cacheable_voter_interface import CacheableVoterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .vote import Vote

__all__ = ["Voter"]


class Voter(CacheableVoterInterface, ABC):
    """Turns "does this voter grant this attribute?" into a single answer.

    Most voters share a shape: for each attribute they recognise, they decide
    yes or no. This template walks the attributes, asks
    :meth:`vote_on_attribute` about each one it :meth:`supports`, and turns the
    yes-or-no answers into the three-valued result — granted the moment one is
    granted, denied when it recognised attributes but granted none, abstained
    when it recognised none.

    It declares itself cacheable but assumes nothing: :meth:`supports_attribute`
    and :meth:`supports_type` say yes to everything, so a plain subclass is
    always consulted. A subclass that knows better narrows them.
    """

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Answer over ``attributes`` by asking :meth:`vote_on_attribute` about each."""
        result = Access.ABSTAIN
        for attribute in attributes:
            if not self.supports(attribute, subject):
                continue
            result = Access.DENIED
            if await self.vote_on_attribute(attribute, subject, token, vote):
                return Access.GRANTED
        return result

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Say yes to any attribute; a subclass that knows better narrows this."""
        del attribute
        return True

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Say yes to any subject type; a subclass that knows better narrows this."""
        del subject_type
        return True

    @abstractmethod
    def supports(self, attribute: object, subject: object) -> bool:
        """Tell whether this voter has anything to say about ``attribute``."""

    @abstractmethod
    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        """Decide whether ``token`` is granted ``attribute`` over ``subject``."""
