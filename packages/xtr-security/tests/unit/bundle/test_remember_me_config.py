"""The remember-me configuration: defaults, options and refusals."""

from __future__ import annotations

from dataclasses import replace

import pytest

from xtr_security.bundle import RememberMeConfig
from xtr_security.exception import InvalidConfigurationError


def test_the_defaults_are_the_signature_handler_and_its_cookie_shape() -> None:
    config = RememberMeConfig()

    assert config.handler == "signature"
    assert config.name == "REMEMBERME"
    assert config.lifetime == 31536000
    assert config.path == "/"
    assert config.domain is None
    assert config.secure is False
    assert config.httponly is True
    assert config.samesite is None
    assert config.always_remember_me is False
    assert config.remember_me_parameter == "_remember_me"
    assert config.signature_properties is None
    assert config.token_provider is None


def test_an_unknown_handler_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match="Unknown remember-me handler"):
        # The literal-typed field is replaced deliberately: the refusal is
        # the behaviour under test, not a type the checker would reject.
        _ = replace(RememberMeConfig(), handler="magic")


def test_the_options_carry_the_cookie_shape_the_handler_reads() -> None:
    config = RememberMeConfig(name="app", lifetime=60, path="/", secure=True)

    options = config.to_options()

    assert options["name"] == "app"
    assert options["lifetime"] == 60
    assert options["secure"] is True
    assert options["always_remember_me"] is False
    assert options["remember_me_parameter"] == "_remember_me"


def test_a_missing_secret_builds_and_holds_its_default() -> None:
    """The bundle must build and boot without the signing secret."""
    config = RememberMeConfig()

    assert config.secret is None
