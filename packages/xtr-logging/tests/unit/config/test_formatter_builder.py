from __future__ import annotations

import pytest

from tests.support.records import make_record
from xtr_logging import LineFormatter
from xtr_logging.config import LineFormatterConfig
from xtr_logging.config.formatter_builder import build_formatter
from xtr_logging.config.services import Services


def test_a_config_builds_its_formatter() -> None:
    assert isinstance(build_formatter(LineFormatterConfig(), Services()), LineFormatter)


def test_the_normalizer_depth_limit_reaches_the_built_formatter() -> None:
    formatter = build_formatter(LineFormatterConfig(format="%context%", max_depth=1), Services())

    line = formatter.format(make_record(context={"a": {"b": {"c": 1}}}))

    assert "Over 1 levels deep" in line


def test_something_that_is_no_config_is_refused_rather_than_built_as_nothing() -> None:
    with pytest.raises(AssertionError):
        # The wrong type is the case under test.
        _ = build_formatter(object(), Services())  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
