"""The consensus strategy weighs grants against denials over every vote."""

from __future__ import annotations

import pytest

from tests.support.streams import counting_stream, stream
from xtr_security_core.authorization import AccessDecisionStrategyInterface, ConsensusStrategy
from xtr_security_core.authorization.voter import Access

GRANTED = Access.GRANTED
DENIED = Access.DENIED
ABSTAIN = Access.ABSTAIN


def test_it_is_an_access_decision_strategy() -> None:
    assert AccessDecisionStrategyInterface in ConsensusStrategy.__mro__


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([GRANTED, GRANTED, DENIED], True),
        ([GRANTED, DENIED, DENIED], False),
        ([ABSTAIN], False),
    ],
)
async def test_it_reduces_votes(results: list[Access], *, expected: bool) -> None:
    assert await ConsensusStrategy().decide(stream(results)) is expected


@pytest.mark.anyio
async def test_a_tie_is_allowed_by_default() -> None:
    assert await ConsensusStrategy().decide(stream([GRANTED, DENIED])) is True


@pytest.mark.anyio
async def test_a_tie_can_be_denied() -> None:
    strategy = ConsensusStrategy(allow_if_equal_granted_denied=False)

    assert await strategy.decide(stream([GRANTED, DENIED])) is False


@pytest.mark.anyio
async def test_it_allows_when_all_abstain_and_the_flag_is_set() -> None:
    assert await ConsensusStrategy(allow_if_all_abstain=True).decide(stream([ABSTAIN])) is True


@pytest.mark.anyio
async def test_it_consumes_every_vote() -> None:
    pulled: list[Access] = []

    result = await ConsensusStrategy().decide(counting_stream([GRANTED, GRANTED, DENIED], pulled))

    assert result is True
    assert pulled == [GRANTED, GRANTED, DENIED]
