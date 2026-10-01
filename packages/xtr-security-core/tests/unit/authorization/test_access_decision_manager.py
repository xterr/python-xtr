"""The decision manager asks the voters and reduces with a strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.voters import ConstantVoter, CountingRoleVoter
from xtr_security_core.authentication.token import NullToken, UsernamePasswordToken
from xtr_security_core.authorization import (
    AccessDecision,
    AccessDecisionManager,
    AccessDecisionManagerInterface,
    ClosureVoter,
    PriorityStrategy,
    RoleVoter,
    UnanimousStrategy,
)
from xtr_security_core.authorization.access_decision_manager import _type_name
from xtr_security_core.authorization.voter import Access
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authorization.is_granted_context import IsGrantedContext


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


def _class_in_module(module: str) -> type[object]:
    probe = type("Probe", (), {})
    probe.__module__ = module
    return probe


def test_it_inherits_the_decision_manager_interface() -> None:
    assert AccessDecisionManagerInterface in AccessDecisionManager.__mro__


@pytest.mark.anyio
async def test_grants_when_a_voter_grants() -> None:
    manager = AccessDecisionManager([RoleVoter()])

    assert await manager.decide(_token("ROLE_USER"), ["ROLE_USER"]) is True


@pytest.mark.anyio
async def test_denies_when_no_voter_grants() -> None:
    manager = AccessDecisionManager([RoleVoter()])

    assert await manager.decide(_token("ROLE_USER"), ["ROLE_ADMIN"]) is False


@pytest.mark.anyio
async def test_defaults_to_the_affirmative_strategy() -> None:
    manager = AccessDecisionManager(
        [ConstantVoter(Access.GRANTED), ConstantVoter(Access.DENIED)],
    )

    assert await manager.decide(NullToken(), ["ANY"]) is True


@pytest.mark.anyio
async def test_honours_the_chosen_strategy() -> None:
    manager = AccessDecisionManager(
        [ConstantVoter(Access.GRANTED), ConstantVoter(Access.DENIED)],
        UnanimousStrategy(),
    )

    assert await manager.decide(NullToken(), ["ANY"]) is False


@pytest.mark.anyio
async def test_more_than_one_attribute_is_refused() -> None:
    manager = AccessDecisionManager([RoleVoter()])

    with pytest.raises(InvalidArgumentError):
        _ = await manager.decide(_token("ROLE_USER"), ["ROLE_USER", "ROLE_ADMIN"])


@pytest.mark.anyio
async def test_zero_attributes_is_refused() -> None:
    manager = AccessDecisionManager([RoleVoter()])

    with pytest.raises(InvalidArgumentError):
        _ = await manager.decide(_token("ROLE_USER"), [])


@pytest.mark.anyio
async def test_a_cacheable_voter_is_consulted_once_per_attribute_and_type() -> None:
    voter = CountingRoleVoter()
    manager = AccessDecisionManager([voter])
    token = _token("ROLE_USER")

    _ = await manager.decide(token, ["ROLE_USER"])
    _ = await manager.decide(token, ["ROLE_USER"])

    assert voter.supports_attribute_calls == 1
    assert voter.supports_type_calls == 1


@pytest.mark.anyio
async def test_a_cacheable_voter_that_does_not_support_is_skipped() -> None:
    voter = CountingRoleVoter()
    manager = AccessDecisionManager([voter])

    result = await manager.decide(_token("ROLE_USER"), ["OTHER"])

    assert result is False
    assert voter.vote_calls == 0


@pytest.mark.anyio
async def test_a_passed_decision_is_filled() -> None:
    manager = AccessDecisionManager([RoleVoter()])
    decision = AccessDecision()

    _ = await manager.decide(_token("ROLE_USER"), ["ROLE_USER"], access_decision=decision)

    assert decision.is_granted is True
    assert len(decision.votes) == 1


@pytest.mark.anyio
async def test_a_nested_decision_reuses_the_outer_record() -> None:
    closure_voter = ClosureVoter()
    manager = AccessDecisionManager([RoleVoter(), closure_voter])

    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_USER")

    decision = AccessDecision()
    _ = await manager.decide(_token("ROLE_USER"), [closure], access_decision=decision)

    assert len(decision.votes) == 3


@pytest.mark.anyio
async def test_a_deciding_first_voter_stops_the_rest_under_priority() -> None:
    first = ConstantVoter(Access.GRANTED)
    second = ConstantVoter(Access.DENIED)
    manager = AccessDecisionManager([first, second], PriorityStrategy())

    granted = await manager.decide(NullToken(), ["ANY"])

    assert granted is True
    assert first.calls == 1
    assert second.calls == 0


@pytest.mark.anyio
async def test_a_passed_decision_gets_the_strategy_name() -> None:
    manager = AccessDecisionManager([RoleVoter()])
    decision = AccessDecision()

    _ = await manager.decide(_token("ROLE_USER"), ["ROLE_USER"], access_decision=decision)

    assert decision.strategy == "AffirmativeStrategy"


@pytest.mark.anyio
async def test_two_same_named_classes_from_different_modules_are_cached_apart() -> None:
    voter = CountingRoleVoter()
    manager = AccessDecisionManager([voter])
    token = _token("ROLE_USER")

    _ = await manager.decide(token, ["ROLE_USER"], subject=_class_in_module("mod_a")())
    _ = await manager.decide(token, ["ROLE_USER"], subject=_class_in_module("mod_b")())

    assert voter.supports_type_calls == 2


def test_type_name_reads_each_branch() -> None:
    assert _type_name(None) == "null"
    assert _type_name(True) == "bool"  # noqa: FBT003
    assert _type_name([1]) == "array"
    assert _type_name(1) == "int"
    assert _type_name(1.0) == "float"
    assert _type_name("s") == "string"
    probe = _class_in_module("mod_a")()
    assert _type_name(probe) == "mod_a.Probe"
