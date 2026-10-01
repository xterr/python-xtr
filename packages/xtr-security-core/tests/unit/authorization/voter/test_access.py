"""The three votes are ordered so a strategy can compare them."""

from __future__ import annotations

from xtr_security_core.authorization.voter import Access


def test_it_orders_granted_above_abstain_above_denied() -> None:
    assert Access.GRANTED > Access.ABSTAIN > Access.DENIED


def test_its_integer_values() -> None:
    assert (Access.GRANTED, Access.ABSTAIN, Access.DENIED) == (1, 0, -1)
