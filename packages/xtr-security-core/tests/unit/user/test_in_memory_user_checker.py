"""The in-memory user checker gates on the account's enabled flag."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import DisabledError
from xtr_security_core.user import (
    InMemoryUser,
    InMemoryUserChecker,
    OidcUser,
    UserCheckerInterface,
)


def test_it_inherits_the_user_checker_interface() -> None:
    assert UserCheckerInterface in InMemoryUserChecker.__mro__


@pytest.mark.anyio
async def test_it_passes_an_enabled_user() -> None:
    await InMemoryUserChecker().check_pre_auth(InMemoryUser("alice", enabled=True))


@pytest.mark.anyio
async def test_it_refuses_a_disabled_user() -> None:
    with pytest.raises(DisabledError):
        await InMemoryUserChecker().check_pre_auth(InMemoryUser("alice", enabled=False))


@pytest.mark.anyio
async def test_it_leaves_a_user_without_the_enabled_flag_alone() -> None:
    await InMemoryUserChecker().check_pre_auth(OidcUser({"sub": "alice"}))


@pytest.mark.anyio
async def test_its_post_auth_does_nothing() -> None:
    await InMemoryUserChecker().check_post_auth(InMemoryUser("alice", enabled=False))
