"""A voter that grants the roles a token holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from .voter import Voter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .vote import Vote

__all__ = ["RoleVoter"]


class RoleVoter(Voter):
    """Grants an attribute when the token holds it as a role.

    Votes only on attributes that start with a prefix — ``ROLE_`` by default —
    and grants one when it is among the token's roles. The prefix keeps it out
    of the way of voters that read other kinds of attribute.
    """

    _prefix: str

    def __init__(self, prefix: str = "ROLE_") -> None:
        """Record the prefix that marks the attributes this voter reads."""
        self._prefix = prefix

    @override
    def supports(self, attribute: object, subject: object) -> bool:
        """Tell whether ``attribute`` is a role name this voter reads."""
        del subject
        return isinstance(attribute, str) and attribute.startswith(self._prefix)

    @override
    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        """Grant ``attribute`` when it is among the token's (expanded) roles."""
        del subject
        roles = self._extract_role_names(token)
        granted = attribute in roles
        if not granted and vote is not None:
            vote.add_reason(f'The token does not have the "{attribute}" role.')
        return granted

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether ``attribute`` carries this voter's prefix."""
        return attribute.startswith(self._prefix)

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject: a role is checked without regard to it."""
        del subject_type
        return True

    def _extract_role_names(self, token: TokenInterface) -> Sequence[str]:
        """Return the roles this voter checks against — the token's own, here."""
        return token.get_role_names()
