"""The keyword grammar of a mailer DSN: groups, spaces, retry periods, and what it refuses."""

from __future__ import annotations

from typing import cast

import pytest
from xtr_http_client import MockHttpClient

from tests.support.dummy_transport_factory import DummyTransportFactory
from tests.unit.transport.test_transport import Shape, shape
from xtr_mailer import InvalidArgumentError
from xtr_mailer.transport import Transport

_A = ("dummy", "a")
_B = ("dummy", "b")
_C = ("dummy", "c")
_SCHEME = "The mailer DSN must contain a scheme."
_GARBAGE = "The mailer DSN has some garbage at the end."


def _build(dsn: str) -> Shape:
    return shape(Transport([DummyTransportFactory(http_client=MockHttpClient())]).from_string(dsn))


def _refusal(dsn: str) -> str:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = _build(dsn)
    return str(caught.value)


@pytest.mark.parametrize(
    "dsn",
    [
        "failover(dummy://a   dummy://b)",
        "failover( dummy://a dummy://b )",
        "  failover(dummy://a dummy://b)  ",
    ],
)
def test_runs_of_spaces_separate_the_members(dsn: str) -> None:
    assert _build(dsn) == ("FailoverTransport", 60, (_A, _B))


def test_spaces_around_a_single_dsn_are_ignored() -> None:
    assert _build("  dummy://a  ") == _A


def test_a_group_of_one_is_a_group() -> None:
    assert _build("failover(dummy://a)") == ("FailoverTransport", 60, (_A,))


def test_a_failover_takes_a_retry_period() -> None:
    assert _build("failover(dummy://a dummy://b)?retry_period=5") == (
        "FailoverTransport",
        5,
        (_A, _B),
    )


def test_a_nested_group_takes_a_retry_period_of_its_own() -> None:
    assert _build("roundrobin(failover(dummy://a dummy://b)?retry_period=5 dummy://c)") == (
        "RoundRobinTransport",
        60,
        (("FailoverTransport", 5, (_A, _B)), _C),
    )


@pytest.mark.parametrize(("raw", "seconds"), [("0", 0), ("1.5", 1.5), ("3600", 3600)])
def test_the_retry_period_is_a_number_of_seconds(raw: str, seconds: float) -> None:
    assert _build(f"failover(dummy://a)?retry_period={raw}")[1] == seconds


def test_a_member_dsn_keeps_its_own_query() -> None:
    assert _build("failover(dummy://a?retry_period=5 dummy://b)") == (
        "FailoverTransport",
        60,
        (_A, _B),
    )


@pytest.mark.parametrize("raw", ["-5", "nan", "NaN", "inf", "abc", "", "1e3", "1_0", "5s"])
def test_it_refuses_a_retry_period_that_is_not_seconds(raw: str) -> None:
    assert _refusal(f"failover(dummy://a)?retry_period={raw}") == (
        f'The "retry_period" option must be a number of seconds, zero or more; "{raw}" is not.'
    )


@pytest.mark.parametrize(
    "dsn",
    [
        "failover(dummy://a)?foo=1",
        "failover(dummy://a)?retry_period=1&foo=1",
        "failover(dummy://a)x",
        "roundrobin(failover(dummy://a)x dummy://b)",
        "dummy://a)",
        "dummy://a dummy://b",
        "failover(dummy://a))",
    ],
)
def test_it_refuses_what_follows_a_transport_but_is_no_part_of_the_dsn(dsn: str) -> None:
    assert _refusal(dsn) == _GARBAGE


@pytest.mark.parametrize(
    "dsn",
    [
        "",
        "   ",
        "failover()",
        "failover( )",
        "failover(dummy://a",
        "roundrobin(failover(dummy://a dummy://b)",
        "failover(other://a",
        "failover(foobar(dummy://a)",
    ],
)
def test_an_empty_member_or_an_unclosed_group_has_no_scheme(dsn: str) -> None:
    assert _refusal(dsn) == _SCHEME


@pytest.mark.parametrize(
    ("dsn", "keyword"),
    [
        ("Failover(dummy://a)", "Failover"),
        ("failover(dummy://a foo(dummy://b))", "foo"),
        ("round_robin(dummy://a)", "round_robin"),
    ],
)
def test_it_refuses_an_unknown_keyword(dsn: str, keyword: str) -> None:
    assert _refusal(dsn) == (
        f'The "{keyword}" keyword is not valid (valid ones are "failover", "roundrobin").'
    )


def test_groups_nest_up_to_the_limit() -> None:
    dsn = "failover(" * 32 + "dummy://a" + ")" * 32

    built = _build(dsn)

    depth = 0
    while built[0] == "FailoverTransport":
        built = _only_member(built)
        depth += 1
    assert (depth, built) == (32, _A)


def _only_member(group: Shape) -> Shape:
    members = group[2]
    assert isinstance(members, tuple)
    (member,) = cast("tuple[Shape]", members)
    return member


def test_it_refuses_groups_nested_deeper_than_the_limit() -> None:
    dsn = "failover(" * 33 + "dummy://a" + ")" * 33

    assert _refusal(dsn) == "The mailer DSN nests its transports more than 32 deep."
