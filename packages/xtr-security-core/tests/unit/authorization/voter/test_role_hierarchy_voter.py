"""The role hierarchy voter grants roles the token reaches."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization.voter import Access, RoleHierarchyVoter, VoterInterface
from xtr_security_core.role import RoleHierarchy
from xtr_security_core.user import InMemoryUser


def test_it_inherits_the_voter_interface() -> None:
    assert VoterInterface in RoleHierarchyVoter.__mro__


@pytest.mark.anyio
async def test_grants_a_reached_role() -> None:
    voter = RoleHierarchyVoter(RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]}))
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_ADMIN"])

    result = await voter.vote(token, None, ["ROLE_USER"])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_denies_a_role_not_reached() -> None:
    voter = RoleHierarchyVoter(RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]}))
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])

    result = await voter.vote(token, None, ["ROLE_ADMIN"])

    assert result is Access.DENIED
