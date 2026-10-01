"""The unknown-firewall error names the firewalls that do exist."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

from xtr_security_http.exception import UnknownFirewallError


def test_it_is_a_security_error_and_a_lookup_error() -> None:
    error = UnknownFirewallError("api", ["docs", "web"])

    assert isinstance(error, SecurityError)
    assert isinstance(error, LookupError)


def test_it_names_the_configured_firewalls() -> None:
    error = UnknownFirewallError("api", ["docs", "web"])

    assert error.name == "api"
    assert error.configured == ("docs", "web")
    assert '"docs"' in str(error)


def test_it_reads_gracefully_with_nothing_configured() -> None:
    assert "none" in str(UnknownFirewallError("api"))
