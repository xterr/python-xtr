"""A refusal in this package's words is found however deep pydantic chained it."""

from __future__ import annotations

from xtr_serializer.exception import NotNormalizableValueError
from xtr_serializer.normalizer._own_words import own_words


def chained(cause: BaseException, depth: int) -> ValueError:
    error = ValueError("pydantic's words")
    error.__cause__ = cause if depth == 1 else chained(cause, depth - 1)
    return error


def test_the_refusal_is_found_at_any_depth() -> None:
    refusal = NotNormalizableValueError("ours")

    assert [own_words(chained(refusal, depth)) for depth in (1, 3)] == [refusal, refusal]


def test_an_error_of_ours_is_its_own_refusal() -> None:
    refusal = NotNormalizableValueError("ours")

    assert own_words(refusal) is refusal


def test_a_chain_without_one_or_looping_gives_none() -> None:
    looping = ValueError("first")
    looping.__cause__ = chained(looping, 2)

    assert own_words(chained(KeyError("theirs"), 2)) is None
    assert own_words(looping) is None
