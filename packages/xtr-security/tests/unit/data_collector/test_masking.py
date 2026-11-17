"""A cloned tree keeps ``******`` under every name like a credential's."""

from __future__ import annotations

from typing import cast, final

from xtr_http_kernel.data_collector import clone_var

from xtr_security.data_collector._masking import MASK, masked


@final
class _Holder:
    __slots__ = ("api_key", "name")

    def __init__(self) -> None:
        self.name = "alice"
        self.api_key = "k-123"


def test_a_mapping_value_under_a_credential_key_is_masked() -> None:
    node = masked(clone_var({"user": "alice", "Password": "hunter2"}))

    assert node["items"] == [
        [clone_var("user"), clone_var("alice")],
        [clone_var("Password"), clone_var(MASK)],
    ]


def test_an_attribute_named_like_a_credential_is_masked() -> None:
    node = masked(clone_var(_Holder()))

    attributes = dict(cast("list[tuple[str, object]]", node["attributes"]))
    assert attributes == {"name": clone_var("alice"), "api_key": clone_var(MASK)}


def test_a_credential_nested_in_a_sequence_is_masked() -> None:
    node = masked(clone_var([{"access_token": "abc"}]))

    assert node["items"] == [
        {
            "kind": "mapping",
            "type": "dict",
            "items": [[clone_var("access_token"), clone_var(MASK)]],
            "truncated": 0,
        }
    ]


def test_a_mapping_keyed_by_something_else_than_text_is_kept() -> None:
    node = clone_var({1: "secret-looking value"})

    assert masked(node) == node


def test_a_scalar_is_kept_as_it_is() -> None:
    node = clone_var(42)

    assert masked(node) is node
