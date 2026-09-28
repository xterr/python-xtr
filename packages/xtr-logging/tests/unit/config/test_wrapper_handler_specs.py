from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError

from xtr_logging.config import (
    FilterHandlerSpec,
    FingersCrossedHandlerSpec,
    GroupHandlerSpec,
    QueueHandlerSpec,
)


def test_a_wrapper_references_the_handler_it_wraps() -> None:
    assert QueueHandlerSpec(handler="file").references == ("file",)


def test_a_group_references_its_members() -> None:
    assert GroupHandlerSpec(members=("a", "b")).references == ("a", "b")


def test_an_action_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = FingersCrossedHandlerSpec(handler="file", action_level="loud")


def test_an_accepted_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = FilterHandlerSpec(handler="file", accepted_levels=("error", "loud"))
