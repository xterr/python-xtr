"""Reading the fields of a state a session kept, refusing one of the wrong type."""

from __future__ import annotations

import pytest

from xtr_security_core._session_state import (
    boolean_field,
    mapping_field,
    optional_boolean_field,
    optional_mapping_field,
    optional_string_field,
    string_field,
    strings_field,
)
from xtr_security_core.exception import InvalidArgumentError


def test_a_string_field_answers_its_string() -> None:
    assert string_field({"firewall": "main"}, "firewall") == "main"


@pytest.mark.parametrize("value", [None, "", 1, ["main"]])
def test_a_string_field_refuses_anything_but_a_non_empty_string(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='"firewall"'):
        _ = string_field({"firewall": value}, "firewall")


def test_a_missing_string_field_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = string_field({}, "firewall")


def test_an_optional_string_field_answers_its_string_or_none() -> None:
    assert optional_string_field({"uri": "/admin"}, "uri") == "/admin"
    assert optional_string_field({"uri": None}, "uri") is None
    assert optional_string_field({}, "uri") is None


def test_an_optional_string_field_refuses_another_type() -> None:
    with pytest.raises(InvalidArgumentError, match='"uri"'):
        _ = optional_string_field({"uri": 1}, "uri")


def test_a_boolean_field_answers_its_boolean() -> None:
    assert boolean_field({"enabled": False}, "enabled") is False


@pytest.mark.parametrize("value", [None, 0, "true"])
def test_a_boolean_field_refuses_anything_but_a_boolean(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='"enabled"'):
        _ = boolean_field({"enabled": value}, "enabled")


def test_an_optional_boolean_field_answers_its_boolean_or_none() -> None:
    assert optional_boolean_field({"verified": True}, "verified") is True
    assert optional_boolean_field({"verified": None}, "verified") is None


def test_an_optional_boolean_field_refuses_another_type() -> None:
    with pytest.raises(InvalidArgumentError, match='"verified"'):
        _ = optional_boolean_field({"verified": 1}, "verified")


def test_a_strings_field_answers_a_list_of_its_own() -> None:
    kept = ["ROLE_USER"]

    roles = strings_field({"roles": kept}, "roles")

    assert roles == ["ROLE_USER"]
    assert roles is not kept


@pytest.mark.parametrize("value", [None, "ROLE_USER", ("ROLE_USER",), ["ROLE_USER", 1]])
def test_a_strings_field_refuses_anything_but_a_list_of_strings(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='"roles"'):
        _ = strings_field({"roles": value}, "roles")


def test_a_mapping_field_answers_a_dictionary_of_its_own() -> None:
    kept: dict[str, object] = {"scope": ["read"]}

    attributes = mapping_field({"attributes": kept}, "attributes")

    assert attributes == {"scope": ["read"]}
    assert attributes is not kept


@pytest.mark.parametrize("value", [None, [], {1: "a"}])
def test_a_mapping_field_refuses_anything_but_an_object_keyed_by_strings(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match='"attributes"'):
        _ = mapping_field({"attributes": value}, "attributes")


def test_an_optional_mapping_field_answers_its_object_or_none() -> None:
    assert optional_mapping_field({"address": {"country": "RO"}}, "address") == {"country": "RO"}
    assert optional_mapping_field({"address": None}, "address") is None


@pytest.mark.parametrize("value", ["RO", {1: "RO"}])
def test_an_optional_mapping_field_refuses_anything_but_an_object_keyed_by_strings(
    value: object,
) -> None:
    with pytest.raises(InvalidArgumentError, match='"address"'):
        _ = optional_mapping_field({"address": value}, "address")
