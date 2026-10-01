"""Voters that record what they were asked, for the decision-manager tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter import Access, RoleVoter, VoterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter import Vote


@final
class ConstantVoter(VoterInterface):
    """Returns a fixed result and counts how many times it was asked."""

    def __init__(self, result: Access) -> None:
        self._result = result
        self.calls = 0

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        del token, subject, attributes, vote
        self.calls += 1
        return self._result


@final
class CountingRoleVoter(RoleVoter):
    """A role voter that counts each applicability and vote call."""

    def __init__(self) -> None:
        super().__init__()
        self.supports_attribute_calls = 0
        self.supports_type_calls = 0
        self.vote_calls = 0

    @override
    def supports_attribute(self, attribute: str) -> bool:
        self.supports_attribute_calls += 1
        return super().supports_attribute(attribute)

    @override
    def supports_type(self, subject_type: str) -> bool:
        self.supports_type_calls += 1
        return super().supports_type(subject_type)

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        self.vote_calls += 1
        return await super().vote(token, subject, attributes, vote)
