from __future__ import annotations

import pytest
from xtr_logging_contracts import InvalidLevelError

from xtr_logging import MixedChannelFilterError
from xtr_logging.config import ConsoleHandlerConfig, StreamHandlerConfig


def test_a_level_that_names_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = StreamHandlerConfig(level="loud")


def test_a_channel_list_mixing_both_forms_is_refused() -> None:
    with pytest.raises(MixedChannelFilterError):
        _ = StreamHandlerConfig(channels=("app", "!event"))


def test_every_channel_is_served_without_a_channel_list() -> None:
    assert StreamHandlerConfig().channel_filter is None


def test_a_handler_that_writes_wraps_no_other() -> None:
    assert StreamHandlerConfig().references == ()


def test_a_console_verbosity_mapped_to_no_level_is_refused() -> None:
    with pytest.raises(InvalidLevelError):
        _ = ConsoleHandlerConfig(verbosity_levels={"verbose": "loud"})
