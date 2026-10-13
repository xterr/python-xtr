"""The context a closure receives: the token, its user, and a checker for nested questions."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import (
    AuthenticatedVoter,
    AuthorizationCheckerInterface,
    IsGrantedContext,
)
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authorization import AccessDecision


@final
class _RecordingChecker(AuthorizationCheckerInterface):
    def __init__(self) -> None:
        self.asked: list[tuple[object, object, AccessDecision | None]] = []

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        self.asked.append((attribute, subject, access_decision))
        return True


def _context(checker: AuthorizationCheckerInterface) -> IsGrantedContext:
    token = UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    return IsGrantedContext(token, token.get_user(), checker)


def test_it_is_an_authorization_checker() -> None:
    assert AuthorizationCheckerInterface in IsGrantedContext.__mro__


def test_it_carries_the_token_and_user() -> None:
    context = _context(_RecordingChecker())

    assert context.token.get_user_identifier() == "alice"
    assert context.user is context.token.get_user()


@pytest.mark.anyio
async def test_is_granted_defers_to_the_checker() -> None:
    checker = _RecordingChecker()

    assert await _context(checker).is_granted("ROLE_USER", "subject") is True
    assert checker.asked == [("ROLE_USER", "subject", None)]


@pytest.mark.anyio
async def test_the_shortcuts_ask_the_authentication_attributes() -> None:
    checker = _RecordingChecker()
    context = _context(checker)

    _ = await context.is_authenticated()
    _ = await context.is_authenticated_fully()
    _ = await context.is_authenticated_recently()
    _ = await context.is_authenticated_very_recently()
    _ = await context.is_impersonator()

    assert [attribute for attribute, _, _ in checker.asked] == [
        AuthenticatedVoter.IS_AUTHENTICATED,
        AuthenticatedVoter.IS_AUTHENTICATED_FULLY,
        AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY,
        AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY,
        AuthenticatedVoter.IS_IMPERSONATOR,
    ]
