from __future__ import annotations

import dataclasses

import pytest

from xtr_notifier.message import MessageOptions


def test_it_defaults_to_no_recipient_and_no_values() -> None:
    options = MessageOptions("slack")

    assert options.kind == "slack"
    assert options.recipient_id is None
    assert dict(options.values) == {}


def test_it_keeps_its_own_copy_of_the_values() -> None:
    values: dict[str, object] = {"channel": "ops"}

    options = MessageOptions("slack", "ops", values)
    values["channel"] = "changed"

    assert options.values == {"channel": "ops"}


def test_two_options_with_the_same_contents_are_equal() -> None:
    assert MessageOptions("slack", "ops", {"a": [1]}) == MessageOptions("slack", "ops", {"a": [1]})


def test_it_is_frozen() -> None:
    options = MessageOptions("slack")

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        options.kind = "telegram"  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_it_is_copied_with_another_recipient() -> None:
    options = MessageOptions("slack", "ops", {"a": 1})

    assert options.with_recipient_id("dev") == MessageOptions("slack", "dev", {"a": 1})
    assert options.recipient_id == "ops"
