from __future__ import annotations

import pytest

from xtr_logging import LineFormatter
from xtr_logging.config import LineFormatterSpec
from xtr_logging.config.formatter_builder import build_formatter
from xtr_logging.config.services import Services


def test_a_spec_builds_its_formatter() -> None:
    assert isinstance(build_formatter(LineFormatterSpec(), Services()), LineFormatter)


def test_something_that_is_no_spec_is_refused_rather_than_built_as_nothing() -> None:
    with pytest.raises(AssertionError):
        # The wrong type is the case under test.
        _ = build_formatter(object(), Services())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
