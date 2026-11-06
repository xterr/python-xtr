"""The login-link configuration: required paths and defaults."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import env

from tests.support.environment import resolved
from xtr_security.bundle import LoginLinkConfig
from xtr_security.exception import InvalidConfigurationError


def test_the_defaults_are_the_link_shape_the_handler_reads() -> None:
    config = LoginLinkConfig(check_path="/login_link", path="/login")

    assert config.lifetime == 600
    assert config.check_post_only is False
    assert tuple(config.signature_properties) == ("password",)
    assert config.secret is None
    assert config.success_handler is None
    assert config.failure_handler is None


def test_an_empty_check_path_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="check path"):
        _ = LoginLinkConfig(check_path="", path="/login")


def test_an_empty_link_path_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="path every minted link"):
        _ = LoginLinkConfig(check_path="/login_link", path="")


def test_both_paths_may_be_read_from_the_environment() -> None:
    config = LoginLinkConfig(check_path=env("LINK_CHECK_PATH"), path=env("LINK_PATH"))

    built = resolved(config, {"LINK_CHECK_PATH": "/login_link", "LINK_PATH": "/login"})

    assert (built.check_path, built.path) == ("/login_link", "/login")
