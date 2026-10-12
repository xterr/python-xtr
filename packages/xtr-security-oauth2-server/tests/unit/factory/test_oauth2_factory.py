"""The factory that opens the firewall key ``oauth2`` on a deployment."""

from __future__ import annotations

from xtr_security_oauth2_server.bundle.oauth2_authenticator_config import (
    OAuth2AuthenticatorConfig,
)
from xtr_security_oauth2_server.factory.oauth2_factory import OAuth2Factory


def test_the_firewall_key_is_the_one_the_reference_bundle_opens() -> None:
    # An application writes OAuth2AuthenticatorConfig() on a firewall, and this
    # key is what makes that mean something.
    assert OAuth2Factory().key == "oauth2"


def test_it_builds_the_configuration_a_firewall_names() -> None:
    assert OAuth2Factory().config_type is OAuth2AuthenticatorConfig


def test_it_runs_late_so_a_deployments_own_authenticator_sees_the_request_first() -> None:
    assert OAuth2Factory().priority < 0
