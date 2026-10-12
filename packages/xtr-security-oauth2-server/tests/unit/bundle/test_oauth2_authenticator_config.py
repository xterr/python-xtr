"""What a firewall writes to accept this server's tokens."""

from __future__ import annotations

from xtr_security_oauth2_server.bundle.oauth2_authenticator_config import (
    OAuth2AuthenticatorConfig,
)


def test_the_firewall_entry_takes_no_options() -> None:
    # A firewall either accepts this server's tokens or it does not.
    assert OAuth2AuthenticatorConfig() == OAuth2AuthenticatorConfig()
