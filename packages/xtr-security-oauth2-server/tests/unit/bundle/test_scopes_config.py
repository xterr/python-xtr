"""The vocabulary of scopes a deployment issues, and what a client starts with."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.bundle.scopes_config import ScopesConfig
from xtr_security_oauth2_server.exception import InvalidConfigurationError


def test_an_empty_name_among_the_available_scopes_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"scopes\.available holds an empty"):
        _ = ScopesConfig(available=("read", ""))


def test_an_empty_name_among_the_default_scopes_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"scopes\.default holds an empty"):
        _ = ScopesConfig(available=("read",), default=("",))


def test_a_repeated_scope_name_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"more than once"):
        _ = ScopesConfig(available=("read", "read"))


def test_a_default_scope_that_is_not_available_is_refused() -> None:
    # Every request for it would be refused by the vocabulary check.
    with pytest.raises(InvalidConfigurationError, match=r"not in scopes\.available"):
        _ = ScopesConfig(available=("read",), default=("write",))


def test_a_default_scope_among_the_available_ones_is_accepted() -> None:
    assert ScopesConfig(available=("read", "write"), default=("read",)).default == ("read",)
