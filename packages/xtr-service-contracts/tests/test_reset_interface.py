from __future__ import annotations

from xtr_service_contracts import ResetInterface


class WithReset:
    def __init__(self) -> None:
        self.items: list[str] = ["stale"]

    def reset(self) -> None:
        self.items.clear()


class WithoutReset:
    def __init__(self) -> None:
        self.count: int = 0

    def increment(self) -> None:
        self.count += 1


def test_a_class_with_reset_is_a_reset_interface() -> None:
    assert isinstance(WithReset(), ResetInterface)


def test_a_class_without_reset_is_not() -> None:
    assert not isinstance(WithoutReset(), ResetInterface)
