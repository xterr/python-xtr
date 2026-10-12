"""A grant reads as its name and compares by it."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.value_object.grant import Grant


def test_it_reads_as_the_grant_it_names() -> None:
    assert str(Grant("authorization_code")) == "authorization_code"


def test_two_grants_of_one_name_are_the_same_grant() -> None:
    assert Grant("password") == Grant("password")


def test_a_grant_of_another_name_is_another_grant() -> None:
    assert Grant("password") != Grant("implicit")


def test_it_can_key_a_mapping() -> None:
    assert {Grant("implicit"): 1}[Grant("implicit")] == 1


def test_it_refuses_a_nameless_grant() -> None:
    with pytest.raises(InvalidArgumentError, match="grant"):
        _ = Grant("")
