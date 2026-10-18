"""The is-granted checker decides a marker's attribute, subject and scopes."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.exception import AccessDeniedError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authorization.oauth2_scope_voter import OAuth2ScopeVoter
from xtr_security_http.decorator.is_granted import IsGranted
from xtr_security_http.resolver.is_granted_checker import IsGrantedChecker

pytestmark = pytest.mark.anyio


def _storage_with_roles(roles: list[str], *, scopes: list[str] | None = None) -> TokenStorage:
    """Return a token storage holding a token with ``roles`` and ``scopes``."""
    storage = TokenStorage()
    token = UsernamePasswordToken(InMemoryUser("ada", roles=roles), "api", roles)
    if scopes is not None:
        token.set_attribute("oauth2_scope", scopes)
    storage.set_token(token)
    return storage


def _checker(storage: TokenStorage) -> IsGrantedChecker:
    return IsGrantedChecker(storage, AccessDecisionManager([RoleVoter(), OAuth2ScopeVoter()]))


async def test_it_grants_the_attribute_the_token_holds() -> None:
    checker = _checker(_storage_with_roles(["ROLE_ADMIN"]))

    await checker.check(IsGranted("ROLE_ADMIN"))


async def test_it_decides_against_the_anonymous_token_without_a_firewall() -> None:
    checker = IsGrantedChecker(TokenStorage(), AccessDecisionManager([RoleVoter()]))

    with pytest.raises(AccessDeniedError):
        await checker.check(IsGranted("ROLE_ADMIN"))


async def test_a_denial_carries_the_attribute_the_subject_and_the_decision() -> None:
    checker = _checker(_storage_with_roles(["ROLE_USER"]))
    subject = object()

    with pytest.raises(AccessDeniedError) as caught:
        await checker.check(IsGranted("ROLE_ADMIN"), subject)

    assert caught.value.attributes == ("ROLE_ADMIN",)
    assert caught.value.subject is subject
    assert caught.value.access_decision is not None
    assert caught.value.access_decision.is_granted is False


async def test_a_denial_answers_the_stated_status_code_directly() -> None:
    checker = _checker(_storage_with_roles(["ROLE_USER"]))

    with pytest.raises(HTTPException) as caught:
        await checker.check(IsGranted("ROLE_ADMIN", status_code=418, message="teapot"))

    assert caught.value.status_code == 418
    assert caught.value.detail == "teapot"


async def test_it_grants_the_opted_in_scopes_the_token_holds() -> None:
    checker = _checker(_storage_with_roles(["ROLE_ADMIN"], scopes=["books:read"]))

    await checker.check(
        IsGranted("ROLE_ADMIN", consume_security_scopes=True),
        security_scopes=("books:read",),
    )


async def test_it_denies_an_opted_in_scope_the_token_lacks() -> None:
    checker = _checker(_storage_with_roles(["ROLE_ADMIN"], scopes=["books:read"]))

    with pytest.raises(AccessDeniedError):
        await checker.check(
            IsGranted("ROLE_ADMIN", consume_security_scopes=True),
            security_scopes=("books:read", "books:write"),
        )
