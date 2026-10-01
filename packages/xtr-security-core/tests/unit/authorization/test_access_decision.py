"""A decision reads granted, or explains why it was denied."""

from __future__ import annotations

from xtr_security_core.authorization import AccessDecision
from xtr_security_core.authorization.voter import Access, Vote


def test_a_granted_decision_says_so() -> None:
    decision = AccessDecision(is_granted=True)

    assert decision.message == "Access granted."


def test_a_denied_decision_without_reasons() -> None:
    decision = AccessDecision(is_granted=False)

    assert decision.message == "Access denied."


def test_a_denied_decision_gathers_the_denying_reasons() -> None:
    denied = Vote(result=Access.DENIED, reasons=["no role"])
    abstained = Vote(result=Access.ABSTAIN, reasons=["ignored"])
    decision = AccessDecision(is_granted=False, votes=[denied, abstained])

    assert decision.message == "Access denied. no role"


def test_defaults() -> None:
    decision = AccessDecision()

    assert decision.is_granted is False
    assert decision.votes == []
    assert decision.strategy is None
