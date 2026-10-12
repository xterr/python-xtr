"""The whole configuration of this bundle: its defaults, and the roles it hands out.

What each half of it is made of is checked beside the module that declares it;
this is about the configuration an application writes as one object.
"""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.bundle.oauth2_server_config import OAuth2ServerConfig
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.model.client import Client


def test_the_whole_configuration_builds_with_no_arguments() -> None:
    # What makes the bundle declarable before an application has written a
    # line of configuration.
    config = OAuth2ServerConfig()

    assert config.persistence is None
    assert config.authorization_server.private_key is None
    assert config.scopes.available == ()
    assert config.client.classname is Client


def test_a_scope_becomes_a_role_under_the_default_prefix() -> None:
    assert OAuth2ServerConfig().role_prefix == "ROLE_OAUTH2_"


def test_an_empty_role_prefix_is_refused() -> None:
    # Without a prefix, a client asking for the scope 'admin' would be granted
    # ROLE_ADMIN.
    with pytest.raises(InvalidConfigurationError, match=r"role_prefix is empty"):
        _ = OAuth2ServerConfig(role_prefix="")
