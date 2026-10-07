from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError

from xtr_logging.config import (
    BufferHandlerConfig,
    FilterHandlerConfig,
    FingersCrossedHandlerConfig,
    GroupHandlerConfig,
    QueueHandlerConfig,
)


def test_a_wrapper_references_the_handler_it_wraps() -> None:
    assert QueueHandlerConfig(handler="file").references == ("file",)


def test_a_group_references_its_members() -> None:
    assert GroupHandlerConfig(members=("a", "b")).references == ("a", "b")


def test_an_action_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = FingersCrossedHandlerConfig(handler="file", action_level="loud")


def test_an_accepted_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = FilterHandlerConfig(handler="file", accepted_levels=("error", "loud"))


def test_buffers_are_bounded_by_default() -> None:
    assert FingersCrossedHandlerConfig(handler="file").buffer_size == 10_000
    assert BufferHandlerConfig(handler="file").buffer_size == 10_000
    assert QueueHandlerConfig(handler="file").max_size == 10_000


def test_a_queue_config_has_no_bubble_field_but_carries_on_error() -> None:
    with pytest.raises(TypeError):
        # A queue handler never bubbles, so the field is gone.
        _ = QueueHandlerConfig(handler="file", bubble=False)  # pyright: ignore[reportCallIssue]  # ty: ignore[unknown-argument]

    assert QueueHandlerConfig(handler="file", on_error="report").on_error == "report"
