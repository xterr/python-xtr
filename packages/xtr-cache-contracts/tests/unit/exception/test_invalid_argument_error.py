from __future__ import annotations

from xtr_cache_contracts import InvalidArgumentError


def test_it_carries_the_reason_and_is_a_value_error() -> None:
    error = InvalidArgumentError("empty key")

    assert error.reason == "empty key"
    assert str(error) == "empty key"
    assert isinstance(error, ValueError)
