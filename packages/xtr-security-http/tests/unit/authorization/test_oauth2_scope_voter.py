"""The OAuth2 scope voter grants by the scopes a token carries."""

from __future__ import annotations

import pytest
from xtr_security_core.authorization.voter import Access, CacheableVoterInterface
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

from xtr_security_http.authenticator.token import PostAuthenticationToken
from xtr_security_http.authorization.oauth2_scope_voter import OAuth2ScopeVoter, oauth2_scope


def test_it_inherits_the_cacheable_voter_interface() -> None:
    assert CacheableVoterInterface in OAuth2ScopeVoter.__mro__


def _token_with_scopes(value: object | None) -> PostAuthenticationToken:
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    if value is not None:
        token.set_attribute("oauth2_scope", value)
    return token


def test_oauth2_scope_builds_the_attribute() -> None:
    assert oauth2_scope("books:read", "books:write") == "OAUTH2_SCOPE(books:read books:write)"


@pytest.mark.anyio
async def test_grants_when_every_scope_is_present_as_a_string() -> None:
    token = _token_with_scopes("books:read books:write")

    result = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:read")])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_grants_when_every_scope_is_present_as_a_list() -> None:
    token = _token_with_scopes(["books:read", "books:write"])

    result = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:read", "books:write")])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_denies_on_partial_scopes() -> None:
    token = _token_with_scopes(["books:read"])

    result = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:read", "books:write")])

    assert result is Access.DENIED


@pytest.mark.anyio
async def test_abstains_when_the_token_carries_no_scopes() -> None:
    token = _token_with_scopes(None)

    result = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:read")])

    assert result is Access.ABSTAIN


@pytest.mark.anyio
async def test_abstains_on_a_non_scope_attribute() -> None:
    token = _token_with_scopes(["books:read"])

    result = await OAuth2ScopeVoter().vote(token, None, ["ROLE_USER"])

    assert result is Access.ABSTAIN


@pytest.mark.anyio
async def test_an_unreadable_scope_attribute_yields_no_scopes() -> None:
    token = _token_with_scopes(123)

    result = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:read")])

    assert result is Access.DENIED


@pytest.mark.anyio
@pytest.mark.parametrize("attribute", ["OAUTH2_SCOPE()", "OAUTH2_SCOPE(   )"])
async def test_a_request_for_no_scopes_abstains(attribute: str) -> None:
    token = _token_with_scopes("books:read")

    result = await OAuth2ScopeVoter().vote(token, None, [attribute])

    assert result is Access.ABSTAIN


@pytest.mark.anyio
async def test_a_denied_vote_names_the_missing_scopes() -> None:
    token = _token_with_scopes(["books:read"])
    vote = Vote()

    _ = await OAuth2ScopeVoter().vote(token, None, [oauth2_scope("books:write")], vote)

    assert any("books:write" in reason for reason in vote.reasons)


def test_oauth2_scope_with_no_scopes_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = oauth2_scope()


def test_supports() -> None:
    voter = OAuth2ScopeVoter()

    assert voter.supports_attribute("OAUTH2_SCOPE(a)") is True
    assert voter.supports_attribute("ROLE_USER") is False
    assert voter.supports_attribute("OAUTH2_SCOPE(a) ") is False
    assert voter.supports_attribute("OAUTH2_SCOPE()") is False
    assert voter.supports_type("anything") is True
