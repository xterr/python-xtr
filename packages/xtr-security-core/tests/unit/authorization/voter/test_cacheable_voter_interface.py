"""The cacheable-voter interface refines the voter interface."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter import (
    Access,
    CacheableVoterInterface,
    RoleVoter,
    VoterInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter import Vote


@final
class _PlainVoter(VoterInterface):
    """A voter that only votes, declaring no applicability."""

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        del token, subject, attributes, vote
        return Access.ABSTAIN


def test_a_cacheable_voter_also_satisfies_the_voter_interface() -> None:
    voter = RoleVoter()

    assert isinstance(voter, CacheableVoterInterface)
    assert isinstance(voter, VoterInterface)


def test_a_plain_voter_without_supports_does_not_satisfy_it() -> None:
    voter = _PlainVoter()

    assert isinstance(voter, VoterInterface)
    assert not isinstance(voter, CacheableVoterInterface)
