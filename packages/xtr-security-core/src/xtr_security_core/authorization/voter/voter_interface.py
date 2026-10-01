"""What a voter answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .access import Access
    from .vote import Vote

__all__ = ["VoterInterface"]


@runtime_checkable
class VoterInterface(Protocol):
    """Answers whether a token may have an attribute over a subject.

    A voter is asked about one access question — an attribute, and the subject
    it concerns — and answers granted, denied, or abstained. It reads whatever
    it needs from the token, and because a voter may check ownership against a
    store, voting is asynchronous.
    """

    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Answer whether ``token`` may have ``attributes`` over ``subject``.

        Args:
            token: The token the decision is being made for.
            subject: The thing the attributes concern, or ``None``.
            attributes: The attributes asked about.
            vote: A record to fill with the reasons behind the answer, if given.
        """
        ...
