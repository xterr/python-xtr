"""The session authentication strategy interface is a runtime-checkable protocol."""

from __future__ import annotations

from xtr_security_http import SessionAuthenticationStrategy, SessionAuthenticationStrategyInterface


def test_the_strategy_satisfies_the_interface() -> None:
    strategy = SessionAuthenticationStrategy(SessionAuthenticationStrategy.MIGRATE)
    assert isinstance(strategy, SessionAuthenticationStrategyInterface)


def test_a_bare_object_does_not_satisfy_the_interface() -> None:
    assert not isinstance(object(), SessionAuthenticationStrategyInterface)
