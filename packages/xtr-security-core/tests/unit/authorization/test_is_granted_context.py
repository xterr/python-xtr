"""The context a closure attribute is handed to decide access with."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.authorization.is_granted_context import IsGrantedContext
from xtr_security_core.user import InMemoryUser


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


def test_it_carries_the_token_and_user() -> None:
    token = _token("ROLE_USER")
    context = IsGrantedContext(token=token, user=token.get_user(), _manager=AccessDecisionManager())

    assert context.token is token
    assert context.user is token.get_user()


@pytest.mark.anyio
async def test_it_defers_a_nested_question_to_the_manager() -> None:
    token = _token("ROLE_USER")
    manager = AccessDecisionManager([RoleVoter()])
    context = IsGrantedContext(token=token, user=token.get_user(), _manager=manager)

    assert await context.is_granted("ROLE_USER") is True
    assert await context.is_granted("ROLE_ADMIN") is False
