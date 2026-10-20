from __future__ import annotations

from xtr_notifier.notification import Importance


def test_its_values_are_the_names_a_policy_is_keyed_by() -> None:
    assert [importance.value for importance in Importance] == ["urgent", "high", "medium", "low"]


def test_it_compares_equal_to_its_name() -> None:
    assert Importance.URGENT == "urgent"
    assert Importance("low") is Importance.LOW
