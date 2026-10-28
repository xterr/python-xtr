"""A marking counts the tokens each place holds."""

from __future__ import annotations

import pytest

from xtr_workflow import Marking
from xtr_workflow.exception import InvalidArgumentError


def test_it_holds_the_places_it_is_built_with() -> None:
    marking = Marking({"a": 1})

    assert marking.has("a")
    assert not marking.has("b")
    assert marking.get_places() == {"a": 1}


def test_marking_a_place_adds_it() -> None:
    marking = Marking({"a": 1})

    marking.mark("b")

    assert marking.has("b")
    assert marking.get_places() == {"a": 1, "b": 1}


def test_marking_a_marked_place_adds_a_token_to_it() -> None:
    marking = Marking({"a": 1})

    marking.mark("a")

    assert marking.get_places() == {"a": 2}


def test_unmarking_a_place_takes_a_token_from_it() -> None:
    marking = Marking({"a": 2})

    marking.unmark("a")

    assert marking.get_places() == {"a": 1}


def test_unmarking_the_last_token_of_a_place_removes_the_place() -> None:
    marking = Marking({"a": 1, "b": 1})

    marking.unmark("a")

    assert not marking.has("a")
    assert marking.get_places() == {"b": 1}


def test_it_keeps_places_in_the_order_they_were_first_marked() -> None:
    marking = Marking({"b": 1})

    marking.mark("a")
    marking.mark("b")

    assert list(marking.get_places()) == ["b", "a"]


def test_it_counts_the_tokens_a_place_holds() -> None:
    assert Marking({"a": 3}).get_token_count("a") == 3


def test_a_place_that_is_not_marked_holds_no_tokens() -> None:
    assert Marking().get_token_count("a") == 0


def test_unmarking_a_place_that_is_not_marked_is_refused() -> None:
    marking = Marking({})

    with pytest.raises(InvalidArgumentError) as raised:
        marking.unmark("a")

    assert str(raised.value) == 'The place "a" is not marked.'


def test_unmarking_more_tokens_than_a_place_holds_is_refused() -> None:
    marking = Marking({"a": 1})

    with pytest.raises(InvalidArgumentError) as raised:
        marking.unmark("a", 2)

    assert str(raised.value) == (
        'The place "a" could not contain a negative token number: '
        '"1" (initial) - "2" (nbToken) = "-1".'
    )


def test_unmarking_fewer_than_one_token_is_refused() -> None:
    marking = Marking({"a": 1})

    with pytest.raises(InvalidArgumentError) as raised:
        marking.unmark("a", 0)

    assert str(raised.value) == 'The number of tokens must be greater than 0, "0" given.'


def test_marking_fewer_than_one_token_is_refused() -> None:
    marking = Marking()

    with pytest.raises(InvalidArgumentError) as raised:
        marking.mark("a", 0)

    assert str(raised.value) == 'The number of tokens must be greater than 0, "0" given.'


def test_changing_the_places_it_returns_leaves_it_unchanged() -> None:
    marking = Marking({"a": 1})

    marking.get_places()["b"] = 1

    assert marking.get_places() == {"a": 1}


def test_its_context_is_empty_until_one_is_set() -> None:
    assert Marking().get_context() == {}


def test_it_keeps_the_context_it_is_given() -> None:
    marking = Marking()

    marking.set_context({"user": "admin"})

    assert marking.get_context() == {"user": "admin"}


def test_changing_the_context_it_returns_leaves_it_unchanged() -> None:
    marking = Marking()
    marking.set_context({"user": "admin"})

    marking.get_context()["user"] = "guest"

    assert marking.get_context() == {"user": "admin"}
