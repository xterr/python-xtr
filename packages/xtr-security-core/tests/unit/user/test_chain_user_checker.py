"""The chain user checker runs each checker in turn, stopping on refusal."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_security_core.exception import DisabledError
from xtr_security_core.user import (
    ChainUserChecker,
    InMemoryUser,
    InMemoryUserChecker,
    UserCheckerInterface,
)

if TYPE_CHECKING:
    from xtr_security_core.authentication.token import TokenInterface
    from xtr_security_core.user import UserInterface


def test_it_inherits_the_user_checker_interface() -> None:
    assert UserCheckerInterface in ChainUserChecker.__mro__


@pytest.mark.anyio
async def test_it_runs_each_pre_auth_in_order() -> None:
    calls: list[str] = []

    @final
    class Recording:
        name: str

        def __init__(self, name: str) -> None:
            self.name = name

        async def check_pre_auth(self, user: UserInterface) -> None:
            del user
            calls.append(self.name)

        async def check_post_auth(
            self,
            user: UserInterface,
            token: TokenInterface | None = None,
        ) -> None:
            del user, token

    chain = ChainUserChecker([Recording("a"), Recording("b")])

    await chain.check_pre_auth(InMemoryUser("alice"))

    assert calls == ["a", "b"]


@pytest.mark.anyio
async def test_it_stops_at_the_first_refusal() -> None:
    chain = ChainUserChecker([InMemoryUserChecker(), InMemoryUserChecker()])

    with pytest.raises(DisabledError):
        await chain.check_pre_auth(InMemoryUser("alice", enabled=False))


@pytest.mark.anyio
async def test_it_runs_each_post_auth() -> None:
    chain = ChainUserChecker([InMemoryUserChecker()])

    await chain.check_post_auth(InMemoryUser("alice"))
