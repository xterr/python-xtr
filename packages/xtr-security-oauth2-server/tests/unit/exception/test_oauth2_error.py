"""``OAuth2Error`` is the one base every error of this library sits under."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import SecurityError

from xtr_security_oauth2_server.exception import OAuth2Error


def test_it_carries_the_message_it_was_raised_with() -> None:
    with pytest.raises(OAuth2Error, match="the grant is not enabled"):
        raise OAuth2Error("the grant is not enabled")


def test_it_derives_from_nothing_but_exception() -> None:
    assert OAuth2Error.__mro__ == (OAuth2Error, Exception, BaseException, object)


def test_it_is_not_one_of_the_security_family_errors() -> None:
    # A protocol answer - a request naming an unknown grant, a code that was
    # already redeemed - is not a failure of the family's authentication
    # machinery. Only the errors a firewall has to answer mix the family's base
    # in beside this one, so `except SecurityError` catches those and no more.
    assert not issubclass(OAuth2Error, SecurityError)
