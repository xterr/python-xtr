"""The exposure level names how much a failure may reveal."""

from __future__ import annotations

from xtr_security_http.authentication import ExposeSecurityLevel


def test_it_has_the_three_levels() -> None:
    assert {level.value for level in ExposeSecurityLevel} == {"none", "account_status", "all"}
