"""The null token stands for nobody authenticated, and refuses to become anybody."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import AbstractToken, NullToken
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.exception import BadMethodCallError
from xtr_security_core.user import InMemoryUser


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in NullToken.__mro__


def test_it_is_not_an_abstract_token() -> None:
    assert AbstractToken not in NullToken.__mro__


def test_it_is_nobody() -> None:
    token = NullToken()

    assert token.get_user() is None
    assert token.get_user_identifier() == ""
    assert token.get_role_names() == ()
    assert str(token) == ""


def test_it_has_no_attributes() -> None:
    token = NullToken()

    assert dict(token.get_attributes()) == {}
    assert token.has_attribute("scope") is False
    assert token.get_attribute("scope") is None


def test_it_has_no_authentication_proofs() -> None:
    assert dict(NullToken().get_authentication_proofs()) == {}


def test_setting_a_user_is_refused() -> None:
    with pytest.raises(BadMethodCallError, match="Cannot set user on a NullToken"):
        NullToken().set_user(InMemoryUser("alice"))


def test_setting_attributes_is_refused() -> None:
    with pytest.raises(BadMethodCallError, match="Cannot set attributes of NullToken"):
        NullToken().set_attributes({"a": 1})


def test_setting_an_attribute_is_refused() -> None:
    with pytest.raises(BadMethodCallError, match="Cannot add attribute to NullToken"):
        NullToken().set_attribute("a", 1)


def test_recording_authentication_proofs_is_refused() -> None:
    with pytest.raises(BadMethodCallError, match="Cannot record authentication proofs"):
        NullToken().set_authentication_proofs({"pwd": 1})
