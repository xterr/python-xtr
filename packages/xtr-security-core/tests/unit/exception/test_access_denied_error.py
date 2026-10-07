"""The access-denied error records what was checked."""

from __future__ import annotations

from xtr_security_core.authorization import Access, AccessDecision, Vote
from xtr_security_core.exception import AccessDeniedError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(AccessDeniedError, SecurityError)


def test_its_defaults() -> None:
    error = AccessDeniedError()

    assert str(error) == "Access Denied."
    assert error.attributes == ()
    assert error.subject is None
    assert error.access_decision is None


def test_it_records_the_attributes_and_subject() -> None:
    subject = object()
    error = AccessDeniedError("nope", attributes=["ROLE_ADMIN"], subject=subject)

    assert error.attributes == ("ROLE_ADMIN",)
    assert error.subject is subject


def test_its_message_includes_the_decision_message() -> None:
    vote = Vote(result=Access.DENIED, reasons=["no such role"])
    decision = AccessDecision(is_granted=False, votes=[vote])

    error = AccessDeniedError("Denied.", access_decision=decision)

    assert "no such role" in str(error)
