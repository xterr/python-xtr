"""A voter that grants the roles a token holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .access import Access
from .cacheable_voter_interface import CacheableVoterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .vote import Vote

__all__ = ["RoleVoter"]


class RoleVoter(CacheableVoterInterface):
    """Votes if any attribute starts with a given prefix — ``ROLE_`` by default.

    Grants one when it is among the token's roles. The prefix keeps it out of
    the way of voters that read other kinds of attribute.
    """

    __slots__: tuple[str, ...] = ("_prefix",)

    _prefix: str

    def __init__(self, prefix: str = "ROLE_") -> None:
        """Record the prefix that marks the attributes this voter reads."""
        self._prefix = prefix

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Grant on the first prefixed attribute among the token's roles; else deny or abstain."""
        del subject
        result = Access.ABSTAIN
        roles = self._extract_roles(token)
        missing_roles: list[str] = []

        for attribute in attributes:
            if not isinstance(attribute, str) or not attribute.startswith(self._prefix):
                continue

            result = Access.DENIED

            if attribute in roles:
                if vote is not None:
                    vote.add_reason(f"The user has {attribute}.")
                return Access.GRANTED

            missing_roles.append(attribute)

        if result is Access.DENIED and vote is not None:
            any_of = " any of" if len(missing_roles) > 1 else ""
            vote.add_reason(f"The user doesn't have{any_of} {', '.join(missing_roles)}.")

        return result

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether ``attribute`` carries this voter's prefix."""
        return attribute.startswith(self._prefix)

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject: a role is checked without regard to it."""
        del subject_type
        return True

    def _extract_roles(self, token: TokenInterface) -> Sequence[str]:
        """Return the roles this voter checks against — the token's own, here."""
        return token.get_role_names()
