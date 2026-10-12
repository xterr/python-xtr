"""``InvalidArgumentError`` refuses a call into the library, and answers nobody."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server_core.exception import InvalidArgumentError, OAuth2Error


def test_it_carries_the_message_it_was_raised_with() -> None:
    with pytest.raises(InvalidArgumentError, match="has no signer"):
        raise InvalidArgumentError("this access token has no signer")


def test_it_sits_under_the_base_of_this_library_and_under_value_error() -> None:
    # Under the base so one `except OAuth2Error` catches it with the rest, and
    # a ValueError so code guarding a call with `except ValueError` keeps
    # working. Nothing of the security family: the firewall answers failed
    # authentication, and a caller's mistake is not that.
    assert InvalidArgumentError.__mro__ == (
        InvalidArgumentError,
        OAuth2Error,
        ValueError,
        Exception,
        BaseException,
        object,
    )
