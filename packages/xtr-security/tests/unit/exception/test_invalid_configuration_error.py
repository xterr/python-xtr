"""The bundle's configuration error derives from the family root and ValueError."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import SecurityError

from xtr_security.exception import InvalidConfigurationError


def test_it_derives_from_the_family_root_and_value_error() -> None:
    for base in (SecurityError, ValueError):
        assert base in InvalidConfigurationError.__mro__


def test_it_is_caught_as_a_security_error() -> None:
    with pytest.raises(SecurityError, match="bad"):
        raise InvalidConfigurationError("bad")
