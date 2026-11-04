"""The reader of DSN groups, on its own; the grammar through the builder is in test_transport_*."""

from __future__ import annotations

import pytest

from xtr_mailer import InvalidArgumentError
from xtr_mailer.transport._dsn_grammar import GARBAGE, MAX_DEPTH, DsnGroup, read_dsn_groups


def test_one_dsn_is_read_as_it_is_written() -> None:
    assert read_dsn_groups(" null://a?x=1 ") == ("null://a?x=1", True)


def test_a_group_is_read_into_its_members_and_retry_period() -> None:
    node, complete = read_dsn_groups("failover(a roundrobin(b c))?retry_period=2.5")

    assert complete
    assert node == DsnGroup("failover", ["a", DsnGroup("roundrobin", ["b", "c"])], retry_period=2.5)


def test_what_follows_a_whole_dsn_is_left_to_the_caller() -> None:
    assert read_dsn_groups("null://a and more") == ("null://a", False)


def test_garbage_after_a_member_of_a_group_is_refused_here() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = read_dsn_groups("failover(failover(a)b)")

    assert str(caught.value) == GARBAGE


def test_groups_nest_thirty_two_deep() -> None:
    assert MAX_DEPTH == 32
