"""The firewall-not-booted error is also a runtime error."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from xtr_security_http.exception import FirewallNotBootedError


def test_it_is_a_security_error() -> None:
    assert issubclass(FirewallNotBootedError, SecurityError)


def test_it_is_a_runtime_error() -> None:
    assert isinstance(FirewallNotBootedError("x"), RuntimeError)
