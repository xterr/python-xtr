from __future__ import annotations

import pytest

from xtr_logging.config import PlaceholderProcessorConfig
from xtr_logging.config.processor_builder import build_processor
from xtr_logging.config.services import Services
from xtr_logging.processor.placeholder_processor import PlaceholderProcessor


def test_a_config_builds_its_processor() -> None:
    assert isinstance(
        build_processor(PlaceholderProcessorConfig(), Services()), PlaceholderProcessor
    )


def test_something_that_is_no_config_is_refused_rather_than_built_as_nothing() -> None:
    with pytest.raises(AssertionError):
        # The wrong type is the case under test.
        _ = build_processor(object(), Services())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
