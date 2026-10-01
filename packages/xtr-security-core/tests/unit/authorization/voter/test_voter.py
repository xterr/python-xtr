"""The abstract voter template and its default applicability."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization.voter import (
    Access,
    CacheableVoterInterface,
    Voter,
    VoterInterface,
)
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter import Vote


def test_it_inherits_its_voter_interfaces() -> None:
    for interface in (VoterInterface, CacheableVoterInterface):
        assert interface in Voter.__mro__


@final
class AlwaysVoter(Voter):
    """A minimal voter that supports one attribute and grants it."""

    @override
    def supports(self, attribute: object, subject: object) -> bool:
        del subject
        return attribute == "GO"

    @override
    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        del attribute, subject, token, vote
        return True


def _token() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])


def test_default_applicability_says_yes_to_everything() -> None:
    voter = AlwaysVoter()

    assert voter.supports_attribute("anything") is True
    assert voter.supports_type("anything") is True


@pytest.mark.anyio
async def test_grants_a_supported_attribute() -> None:
    assert await AlwaysVoter().vote(_token(), None, ["GO"]) is Access.GRANTED


@pytest.mark.anyio
async def test_abstains_on_an_unsupported_attribute() -> None:
    assert await AlwaysVoter().vote(_token(), None, ["NO"]) is Access.ABSTAIN
