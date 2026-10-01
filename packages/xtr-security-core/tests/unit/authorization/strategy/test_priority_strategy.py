"""The priority strategy settles on the first opinion, stopping there."""

from __future__ import annotations

import pytest

from tests.support.streams import counting_stream, stream
from xtr_security_core.authorization import AccessDecisionStrategyInterface, PriorityStrategy
from xtr_security_core.authorization.voter import Access

GRANTED = Access.GRANTED
DENIED = Access.DENIED
ABSTAIN = Access.ABSTAIN


def test_it_is_an_access_decision_strategy() -> None:
    assert AccessDecisionStrategyInterface in PriorityStrategy.__mro__


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([ABSTAIN, GRANTED, DENIED], True),
        ([ABSTAIN, DENIED, GRANTED], False),
        ([ABSTAIN], False),
    ],
)
async def test_it_reduces_votes(results: list[Access], *, expected: bool) -> None:
    assert await PriorityStrategy().decide(stream(results)) is expected


@pytest.mark.anyio
async def test_it_allows_when_all_abstain_and_the_flag_is_set() -> None:
    assert await PriorityStrategy(allow_if_all_abstain=True).decide(stream([ABSTAIN])) is True


@pytest.mark.anyio
async def test_it_stops_pulling_at_the_first_opinion() -> None:
    pulled: list[Access] = []

    result = await PriorityStrategy().decide(counting_stream([ABSTAIN, GRANTED, DENIED], pulled))

    assert result is True
    assert pulled == [ABSTAIN, GRANTED]
