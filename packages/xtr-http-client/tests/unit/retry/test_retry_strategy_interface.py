from __future__ import annotations

from xtr_http_client.retry import GenericRetryStrategy, RetryStrategyInterface


def test_a_strategy_is_recognised_by_the_two_methods_it_answers_with() -> None:
    assert isinstance(GenericRetryStrategy(), RetryStrategyInterface)


def test_something_answering_neither_is_not_a_strategy() -> None:
    assert not isinstance(object(), RetryStrategyInterface)
