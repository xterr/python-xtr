"""Sensitive authentication failures are hidden by the exposure level."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    CustomUserMessageAccountStatusError,
    DisabledError,
    UserNotFoundError,
)

from xtr_security_http.authentication import ExposeSecurityLevel, is_sensitive, mask

NONE = ExposeSecurityLevel.NONE
ACCOUNT_STATUS = ExposeSecurityLevel.ACCOUNT_STATUS
ALL = ExposeSecurityLevel.ALL


@pytest.mark.parametrize(
    ("error", "level", "expected"),
    [
        (UserNotFoundError("alice"), NONE, True),
        (UserNotFoundError("alice"), ACCOUNT_STATUS, True),
        (UserNotFoundError("alice"), ALL, False),
        (DisabledError(), NONE, True),
        (DisabledError(), ACCOUNT_STATUS, False),
        (DisabledError(), ALL, False),
        (CustomUserMessageAccountStatusError("shown"), NONE, False),
        (BadCredentialsError(), NONE, False),
    ],
)
def test_is_sensitive(
    error: AuthenticationError, level: ExposeSecurityLevel, *, expected: bool
) -> None:
    assert is_sensitive(error, level) is expected


def test_mask_replaces_a_sensitive_error_and_chains_the_cause() -> None:
    original = UserNotFoundError("alice")

    masked = mask(original, NONE)

    assert isinstance(masked, BadCredentialsError)
    assert masked.__cause__ is original


def test_mask_suppresses_the_implicit_context() -> None:
    masked = mask(UserNotFoundError("alice"), NONE)

    assert masked.__suppress_context__ is True


def test_mask_leaves_a_non_sensitive_error_alone() -> None:
    original = BadCredentialsError()

    assert mask(original, NONE) is original


def test_mask_reveals_everything_at_all() -> None:
    original = UserNotFoundError("alice")

    assert mask(original, ALL) is original
