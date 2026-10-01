"""The authenticated voter grants by a token's authentication strength."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication import AuthenticationTrustResolver
from xtr_security_core.authentication.token import NullToken, UsernamePasswordToken
from xtr_security_core.authorization.voter import (
    Access,
    AuthenticatedVoter,
    CacheableVoterInterface,
)
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.user import InMemoryUser


def test_it_inherits_the_cacheable_voter_interface() -> None:
    assert CacheableVoterInterface in AuthenticatedVoter.__mro__


def _voter() -> AuthenticatedVoter:
    return AuthenticatedVoter(AuthenticationTrustResolver())


def _real_token() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])


@pytest.mark.anyio
async def test_public_access_is_always_granted() -> None:
    result = await _voter().vote(NullToken(), None, [AuthenticatedVoter.PUBLIC_ACCESS])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_is_authenticated_granted_for_a_real_token() -> None:
    result = await _voter().vote(_real_token(), None, [AuthenticatedVoter.IS_AUTHENTICATED])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_is_authenticated_denied_for_the_null_token() -> None:
    result = await _voter().vote(NullToken(), None, [AuthenticatedVoter.IS_AUTHENTICATED])

    assert result is Access.DENIED


@pytest.mark.anyio
async def test_is_authenticated_fully_granted_for_a_real_token() -> None:
    result = await _voter().vote(_real_token(), None, [AuthenticatedVoter.IS_AUTHENTICATED_FULLY])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_abstains_on_an_unrelated_attribute() -> None:
    result = await _voter().vote(_real_token(), None, ["ROLE_USER"])

    assert result is Access.ABSTAIN


@pytest.mark.anyio
async def test_a_denied_vote_names_the_failed_attribute() -> None:
    vote = Vote()

    _ = await _voter().vote(NullToken(), None, [AuthenticatedVoter.IS_AUTHENTICATED], vote)

    assert any(AuthenticatedVoter.IS_AUTHENTICATED in reason for reason in vote.reasons)


def test_supports() -> None:
    voter = _voter()

    assert voter.supports_attribute(AuthenticatedVoter.IS_AUTHENTICATED) is True
    assert voter.supports_attribute("ROLE_USER") is False
    assert voter.supports_type("anything") is True
