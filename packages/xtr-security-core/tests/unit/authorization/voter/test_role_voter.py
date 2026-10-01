"""The role voter grants a role the token holds."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization.voter import (
    Access,
    CacheableVoterInterface,
    RoleVoter,
    Vote,
    VoterInterface,
)
from xtr_security_core.user import InMemoryUser


def test_it_inherits_its_voter_interfaces() -> None:
    for interface in (VoterInterface, CacheableVoterInterface):
        assert interface in RoleVoter.__mro__


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


@pytest.mark.anyio
async def test_grants_a_held_role() -> None:
    result = await RoleVoter().vote(_token("ROLE_USER"), None, ["ROLE_USER"])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_denies_a_role_not_held() -> None:
    vote = Vote()

    result = await RoleVoter().vote(_token("ROLE_USER"), None, ["ROLE_ADMIN"], vote)

    assert result is Access.DENIED
    assert vote.reasons


@pytest.mark.anyio
async def test_abstains_on_a_non_role_attribute() -> None:
    result = await RoleVoter().vote(_token("ROLE_USER"), None, ["OTHER"])

    assert result is Access.ABSTAIN


def test_supports_by_prefix() -> None:
    voter = RoleVoter()

    assert voter.supports_attribute("ROLE_X") is True
    assert voter.supports_attribute("OTHER") is False
    assert voter.supports_type("anything") is True


@pytest.mark.anyio
async def test_a_custom_prefix() -> None:
    result = await RoleVoter(prefix="SCOPE_").vote(_token("SCOPE_READ"), None, ["SCOPE_READ"])

    assert result is Access.GRANTED
