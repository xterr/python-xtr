"""The refusal a deployment's own mistake is reported as."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception.oauth2_error import OAuth2Error
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)


def test_one_except_for_this_library_catches_it() -> None:
    with pytest.raises(OAuth2Error):
        raise InvalidConfigurationError("something a deployment got wrong")


def test_a_configuration_this_server_cannot_read_is_a_bad_argument() -> None:
    with pytest.raises(ValueError, match=r"something a deployment got wrong"):
        raise InvalidConfigurationError("something a deployment got wrong")


def test_it_is_not_a_refusal_a_client_is_waiting_for() -> None:
    # No client caused this and no client is waiting for it, so the firewall
    # and the endpoints must not answer it as a protocol error.
    assert not issubclass(InvalidConfigurationError, OAuthServerError)


def test_it_says_what_it_was_given() -> None:
    assert str(InvalidConfigurationError("name the setting")) == "name the setting"
