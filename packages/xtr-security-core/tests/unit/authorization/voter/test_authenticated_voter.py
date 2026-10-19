"""The authenticated voter grants by how strongly, and how recently, a token authenticated."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_clock import MockClock

from xtr_security_core.authentication import AuthenticationMethod, AuthenticationTrustResolver
from xtr_security_core.authentication.token import (
    AbstractToken,
    NullToken,
    OfflineTokenInterface,
    SwitchUserToken,
    UsernamePasswordToken,
)
from xtr_security_core.authorization.voter import (
    Access,
    AuthenticatedVoter,
    CacheableVoterInterface,
)
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_NOW_TS = int(_NOW.timestamp())


@final
class _Offline(AbstractToken, OfflineTokenInterface):
    __slots__ = ()


@final
class _RememberingResolver(AuthenticationTrustResolver):
    """A resolver for which every authenticated token was remembered."""

    __slots__ = ()

    @override
    def is_remember_me(self, token: TokenInterface | None = None) -> bool:
        return self.is_authenticated(token)


def test_it_inherits_the_cacheable_voter_interface() -> None:
    assert CacheableVoterInterface in AuthenticatedVoter.__mro__


def _voter() -> AuthenticatedVoter:
    return AuthenticatedVoter(AuthenticationTrustResolver(clock=MockClock(_NOW)))


def _real_token(proven_at: int | None = None) -> UsernamePasswordToken:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    if proven_at is not None:
        token.set_authentication_proofs({AuthenticationMethod.PASSWORD: proven_at})
    return token


async def _vote(token: TokenInterface, *attributes: object) -> tuple[Access, Vote]:
    vote = Vote()
    result = await _voter().vote(token, None, list(attributes), vote)
    return result, vote


@pytest.mark.anyio
async def test_public_access_alone_is_always_granted() -> None:
    result, vote = await _vote(NullToken(), AuthenticatedVoter.PUBLIC_ACCESS)

    assert result is Access.GRANTED
    assert vote.reasons == ["Access is public."]


@pytest.mark.anyio
async def test_public_access_among_other_attributes_is_not_granted_on_its_own() -> None:
    result, _ = await _vote(NullToken(), AuthenticatedVoter.PUBLIC_ACCESS, "ROLE_USER")

    assert result is Access.ABSTAIN


@pytest.mark.anyio
async def test_is_authenticated_granted_for_a_token_with_a_user() -> None:
    result, vote = await _vote(_real_token(), AuthenticatedVoter.IS_AUTHENTICATED)

    assert result is Access.GRANTED
    assert vote.reasons == ["The user is authenticated."]


@pytest.mark.anyio
async def test_is_authenticated_denied_for_the_null_token() -> None:
    result, vote = await _vote(NullToken(), AuthenticatedVoter.IS_AUTHENTICATED)

    assert result is Access.DENIED
    assert vote.reasons == ["The user is not authenticated."]


@pytest.mark.anyio
async def test_is_authenticated_fully_granted_for_a_token_with_a_user() -> None:
    result, vote = await _vote(_real_token(), AuthenticatedVoter.IS_AUTHENTICATED_FULLY)

    assert result is Access.GRANTED
    assert vote.reasons == ["The user is fully authenticated."]


@pytest.mark.anyio
async def test_is_authenticated_remembered_granted_for_a_fully_authenticated_token() -> None:
    result, vote = await _vote(_real_token(), AuthenticatedVoter.IS_AUTHENTICATED_REMEMBERED)

    assert result is Access.GRANTED
    assert vote.reasons == ["The user is fully authenticated."]


@pytest.mark.anyio
async def test_a_remembered_token_is_remembered_but_not_fully_authenticated() -> None:
    voter = AuthenticatedVoter(_RememberingResolver())
    vote = Vote()

    remembered = await voter.vote(_real_token(), None, [AuthenticatedVoter.IS_REMEMBERED], vote)
    fully = await voter.vote(_real_token(), None, [AuthenticatedVoter.IS_AUTHENTICATED_FULLY])
    either = await voter.vote(_real_token(), None, [AuthenticatedVoter.IS_AUTHENTICATED_REMEMBERED])

    assert remembered is Access.GRANTED
    assert vote.reasons == ["The user is remembered."]
    assert fully is Access.DENIED
    assert either is Access.GRANTED


@pytest.mark.anyio
async def test_is_remembered_denied_when_not_remembered() -> None:
    result, vote = await _vote(_real_token(), AuthenticatedVoter.IS_REMEMBERED)

    assert result is Access.DENIED
    assert vote.reasons == ["The user is not remembered."]


@pytest.mark.anyio
async def test_is_impersonator_granted_for_a_switch_user_token() -> None:
    token = SwitchUserToken(InMemoryUser("alice"), "api", ["ROLE_USER"], _real_token())
    result, vote = await _vote(token, AuthenticatedVoter.IS_IMPERSONATOR)

    assert result is Access.GRANTED
    assert vote.reasons == ["The user is impersonating another user."]


@pytest.mark.anyio
async def test_is_impersonator_denied_for_a_plain_token() -> None:
    result, vote = await _vote(_real_token(), AuthenticatedVoter.IS_IMPERSONATOR)

    assert result is Access.DENIED
    assert vote.reasons == ["The user is not impersonating another user."]


@pytest.mark.anyio
async def test_is_authenticated_recently_granted_within_the_window() -> None:
    result, vote = await _vote(
        _real_token(_NOW_TS - 60), AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY
    )

    assert result is Access.GRANTED
    assert vote.reasons == ["The user authenticated recently."]


@pytest.mark.anyio
async def test_is_authenticated_very_recently_granted_within_the_window() -> None:
    result, vote = await _vote(
        _real_token(_NOW_TS - 60), AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY
    )

    assert result is Access.GRANTED
    assert vote.reasons == ["The user authenticated very recently."]


@pytest.mark.anyio
async def test_a_stale_proof_is_denied_and_requests_a_re_authentication() -> None:
    result, vote = await _vote(
        _real_token(_NOW_TS - 3 * 3600), AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY
    )

    assert result is Access.DENIED
    assert vote.reasons == ["The user is not authenticated recently enough."]
    assert vote.re_authentication_attribute == AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY


@pytest.mark.anyio
async def test_the_very_recent_attribute_is_preferred_for_re_authentication() -> None:
    result, vote = await _vote(
        _real_token(),
        AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY,
        AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY,
    )

    assert result is Access.DENIED
    assert vote.reasons == ["The user did not authenticate very recently."]
    assert vote.re_authentication_attribute == AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY


@pytest.mark.anyio
async def test_a_remembered_token_is_never_recent() -> None:
    voter = AuthenticatedVoter(_RememberingResolver(clock=MockClock(_NOW)))

    result = await voter.vote(
        _real_token(_NOW_TS), None, [AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY]
    )

    assert result is Access.DENIED


@pytest.mark.anyio
async def test_only_the_strictest_denial_reason_is_reported() -> None:
    result, vote = await _vote(
        NullToken(),
        AuthenticatedVoter.IS_AUTHENTICATED,
        AuthenticatedVoter.IS_AUTHENTICATED_FULLY,
    )

    assert result is Access.DENIED
    assert vote.reasons == ["The user is not fully authenticated."]


@pytest.mark.anyio
async def test_an_offline_token_with_a_user_is_refused() -> None:
    token = _Offline(["ROLE_USER"])
    token.set_user(InMemoryUser("bob"))

    with pytest.raises(InvalidArgumentError, match="offline token"):
        _ = await _vote(token, AuthenticatedVoter.IS_AUTHENTICATED)


@pytest.mark.anyio
async def test_an_offline_guest_token_is_simply_not_authenticated() -> None:
    result, _ = await _vote(_Offline(), AuthenticatedVoter.IS_AUTHENTICATED)

    assert result is Access.DENIED


@pytest.mark.anyio
async def test_abstains_on_an_unrelated_attribute() -> None:
    result, vote = await _vote(_real_token(), "ROLE_USER", 42)

    assert result is Access.ABSTAIN
    assert vote.reasons == []


def test_supports_every_attribute_it_reads() -> None:
    voter = _voter()

    for attribute in (
        AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY,
        AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY,
        AuthenticatedVoter.IS_AUTHENTICATED_FULLY,
        AuthenticatedVoter.IS_AUTHENTICATED_REMEMBERED,
        AuthenticatedVoter.IS_AUTHENTICATED,
        AuthenticatedVoter.IS_IMPERSONATOR,
        AuthenticatedVoter.IS_REMEMBERED,
        AuthenticatedVoter.PUBLIC_ACCESS,
    ):
        assert voter.supports_attribute(attribute) is True
    assert voter.supports_attribute("ROLE_USER") is False
    assert voter.supports_type("anything") is True
