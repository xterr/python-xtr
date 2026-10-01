"""The unanimous strategy refuses on the first denial, stopping there."""

from __future__ import annotations

import pytest

from tests.support.streams import counting_stream, stream
from xtr_security_core.authorization import AccessDecisionStrategyInterface, UnanimousStrategy
from xtr_security_core.authorization.voter import Access

GRANTED = Access.GRANTED
DENIED = Access.DENIED
ABSTAIN = Access.ABSTAIN


def test_it_is_an_access_decision_strategy() -> None:
    assert AccessDecisionStrategyInterface in UnanimousStrategy.__mro__


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ([GRANTED, GRANTED], True),
        ([GRANTED, DENIED], False),
        ([ABSTAIN], False),
    ],
)
async def test_it_reduces_votes(results: list[Access], *, expected: bool) -> None:
    assert await UnanimousStrategy().decide(stream(results)) is expected


@pytest.mark.anyio
async def test_it_allows_when_all_abstain_and_the_flag_is_set() -> None:
    assert await UnanimousStrategy(allow_if_all_abstain=True).decide(stream([ABSTAIN])) is True


@pytest.mark.anyio
async def test_it_stops_pulling_at_the_first_denial() -> None:
    pulled: list[Access] = []

    result = await UnanimousStrategy().decide(counting_stream([DENIED, GRANTED], pulled))

    assert result is False
    assert pulled == [DENIED]
