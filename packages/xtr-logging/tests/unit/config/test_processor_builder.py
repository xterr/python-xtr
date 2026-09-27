from __future__ import annotations

import pytest

from xtr_logging.config import PlaceholderProcessorSpec
from xtr_logging.config.processor_builder import build_processor
from xtr_logging.config.services import Services
from xtr_logging.processor.placeholder_processor import PlaceholderProcessor


def test_a_spec_builds_its_processor() -> None:
    assert isinstance(build_processor(PlaceholderProcessorSpec(), Services()), PlaceholderProcessor)


def test_something_that_is_no_spec_is_refused_rather_than_built_as_nothing() -> None:
    with pytest.raises(AssertionError):
        _ = build_processor(object(), Services())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
