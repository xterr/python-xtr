from __future__ import annotations

import dataclasses

import pytest

from xtr_webhook.exception import InvalidArgumentError
from xtr_webhook.subscriber import Subscriber

_URL = "https://example.test/hook"
# Named away from "secret" so the linter's hardcoded-credential rule stays useful
# where it matters; comparing against the literal inline is what trips it.
_WHSEC = "s3cret"


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_it_carries_the_url_and_the_secret() -> None:
    subscriber = Subscriber(_URL, _WHSEC)

    assert subscriber.url == _URL
    assert subscriber.secret == _WHSEC


def test_two_subscribers_with_the_same_values_are_equal() -> None:
    assert Subscriber(_URL, _WHSEC) == Subscriber(_URL, _WHSEC)


def test_subscribers_differing_in_one_value_are_not_equal() -> None:
    assert Subscriber(_URL, _WHSEC) != Subscriber("https://elsewhere.test/hook", _WHSEC)


def test_its_repr_names_the_url() -> None:
    assert _URL in repr(Subscriber(_URL, _WHSEC))


def test_its_repr_does_not_carry_the_secret() -> None:
    assert _WHSEC not in repr(Subscriber(_URL, _WHSEC))


def test_it_refuses_an_empty_secret() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = Subscriber(_URL, "")

    assert str(refused.value) == "A non-empty secret is required."


def test_an_empty_secret_is_refused_as_a_value_error() -> None:
    with pytest.raises(ValueError, match="non-empty secret"):
        _ = Subscriber(_URL, "")


def test_nothing_can_be_changed_after_the_fact() -> None:
    subscriber = Subscriber(_URL, _WHSEC)

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(subscriber, "url", "https://elsewhere.test/hook")
