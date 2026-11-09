"""The stand-in codec keeps a nested token by its place and hands the same one back."""

from __future__ import annotations

import pytest

from tests.support.nested_tokens import NestedTokens, nests_nothing
from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.user import InMemoryUser


def test_a_kept_token_is_handed_back_by_its_place() -> None:
    codec = NestedTokens()
    token = UsernamePasswordToken(InMemoryUser("alice"), "main")

    assert codec.decode(codec.encode(token)) is token


@pytest.mark.parametrize("value", [None, "place", {"place": 0}, {"place": "0"}])
def test_a_place_nothing_is_kept_at_hands_back_nothing(value: object) -> None:
    assert NestedTokens().decode(value) is None


def test_asking_the_failing_codec_fails_the_test() -> None:
    with pytest.raises(AssertionError):
        nests_nothing({"place": 0})
