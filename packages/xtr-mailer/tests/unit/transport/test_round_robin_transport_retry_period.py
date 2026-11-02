"""The retry period a round-robin or failover transport rests a dead transport for."""

from __future__ import annotations

import math

import pytest

from tests.support.fake_transport import FakeTransport
from xtr_mailer import InvalidArgumentError
from xtr_mailer.transport import FailoverTransport, RoundRobinTransport


@pytest.mark.parametrize("group", [RoundRobinTransport, FailoverTransport])
@pytest.mark.parametrize(("retry_period", "shown"), [(-1, "-1"), (-0.5, "-0.5"), (math.nan, "nan")])
def test_it_refuses_a_retry_period_that_is_not_zero_or_more_seconds(
    group: type[RoundRobinTransport], retry_period: float, shown: str
) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = group([FakeTransport()], retry_period)

    assert str(caught.value) == (
        f"The retry period must be a number of seconds, zero or more; {shown} is not."
    )


@pytest.mark.parametrize("retry_period", [0, 0.5, 60, math.inf])
def test_it_takes_a_retry_period_of_zero_or_more_seconds(retry_period: float) -> None:
    assert RoundRobinTransport([FakeTransport()], retry_period)._retry_period == retry_period
