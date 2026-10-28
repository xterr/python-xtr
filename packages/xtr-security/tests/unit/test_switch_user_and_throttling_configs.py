"""The switch-user and login-throttling firewall blocks: defaults."""

from __future__ import annotations

from xtr_security.bundle import FirewallConfig
from xtr_security.login_throttling_config import LoginThrottlingConfig
from xtr_security.switch_user_config import SwitchUserConfig


def test_the_switch_user_defaults_are_the_listener_shape() -> None:
    config = SwitchUserConfig()

    assert config.role == "ROLE_ALLOWED_TO_SWITCH"
    assert config.parameter == "_switch_user"
    assert config.enable_csrf is False
    assert config.csrf_parameter == "_csrf_token"
    assert config.csrf_token_id == "switch_user"
    assert config.path is None


def test_the_throttling_defaults_are_two_five_attempt_windows() -> None:
    config = LoginThrottlingConfig()

    assert config.secret is None
    assert config.global_limit == 5
    assert config.global_interval == "15 minutes"
    assert config.local_limit == 5
    assert config.local_interval == "15 minutes"


def test_a_firewall_carries_both_blocks_beside_its_logout() -> None:
    firewall = FirewallConfig(
        pattern=r"^/",
        security=False,
        switch_user=SwitchUserConfig(),
        login_throttling=LoginThrottlingConfig(),
    )

    assert firewall.switch_user is not None
    assert firewall.login_throttling is not None
    assert firewall.logout is None
