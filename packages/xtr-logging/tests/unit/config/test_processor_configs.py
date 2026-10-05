from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError

from xtr_logging import InvalidOptionError
from xtr_logging.config import IntrospectionProcessorConfig, UidProcessorConfig


def test_a_processor_targets_a_channel_or_a_handler_not_both() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessorConfig(channel="app", handler="file")


def test_an_introspection_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = IntrospectionProcessorConfig(level="loud")
