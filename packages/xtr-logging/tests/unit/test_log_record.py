from __future__ import annotations

import dataclasses

import pytest

from tests.support.records import make_record
from xtr_logging import Level


def test_context_is_copied_so_the_caller_cannot_rewrite_it() -> None:
    context: dict[str, object] = {"user": 1}
    record = make_record(context=context)

    context["user"] = 2

    assert record.context["user"] == 1


def test_context_cannot_be_mutated_through_the_record() -> None:
    record = make_record(context={"user": 1})

    with pytest.raises(TypeError):
        record.context["user"] = 2  # pyright: ignore[reportIndexIssue]  # ty: ignore[invalid-assignment]


def test_a_record_is_frozen() -> None:
    record = make_record()

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.message = "changed"  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_with_extra_merges_and_leaves_the_original_alone() -> None:
    record = make_record(extra={"a": 1, "b": 2})

    enriched = record.with_extra({"b": 3, "c": 4})

    assert dict(enriched.extra) == {"a": 1, "b": 3, "c": 4}
    assert dict(record.extra) == {"a": 1, "b": 2}


def test_exception_is_read_from_the_reserved_key() -> None:
    error = RuntimeError("boom")

    record = make_record(context={"exception": error})

    assert record.exception is error


def test_exception_is_none_when_the_key_holds_something_else() -> None:
    assert make_record(context={"exception": "not one"}).exception is None


def test_level_name_is_upper_case() -> None:
    assert make_record(Level.NOTICE).level_name == "NOTICE"
