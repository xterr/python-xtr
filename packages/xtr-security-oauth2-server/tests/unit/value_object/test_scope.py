"""A scope reads as its name and compares by it."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.value_object.scope import Scope


def test_it_reads_as_the_scope_it_names() -> None:
    assert str(Scope("read")) == "read"


def test_two_scopes_of_one_name_are_the_same_scope() -> None:
    assert Scope("read") == Scope("read")


def test_a_scope_of_another_name_is_another_scope() -> None:
    assert Scope("read") != Scope("write")


def test_it_can_key_a_mapping() -> None:
    assert {Scope("read"): 1}[Scope("read")] == 1


def test_it_refuses_a_nameless_scope() -> None:
    with pytest.raises(InvalidArgumentError, match="scope"):
        _ = Scope("")
