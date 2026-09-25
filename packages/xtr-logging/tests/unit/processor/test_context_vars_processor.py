from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.records import make_record
from xtr_logging.log_context import bind_context, clear_context
from xtr_logging.processor.context_vars_processor import ContextVarsProcessor

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clean_context() -> Iterator[None]:
    clear_context()
    yield
    clear_context()


def test_the_bound_context_is_merged_into_extra_flat() -> None:
    # Given a value bound in the ambient context
    bind_context({"request_id": "r1"})

    # When a record is processed with no key
    record = ContextVarsProcessor()(make_record())

    # Then the value sits directly in extra
    assert record.extra["request_id"] == "r1"


def test_the_bound_context_can_be_nested_under_a_key() -> None:
    # Given a value bound in the ambient context
    bind_context({"request_id": "r1"})

    # When a record is processed under a key
    record = ContextVarsProcessor("ctx")(make_record())

    # Then the whole context is nested there
    assert record.extra["ctx"] == {"request_id": "r1"}


def test_an_empty_context_adds_nothing() -> None:
    # Given nothing is bound
    record = make_record()

    # When a record is processed
    result = ContextVarsProcessor()(record)

    # Then the very same record comes back
    assert result is record
