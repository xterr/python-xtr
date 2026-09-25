from __future__ import annotations

import pytest

from xtr_logging.config import ChannelFilter
from xtr_logging.exception.mixed_channel_filter_error import MixedChannelFilterError


@pytest.mark.parametrize("value", [None, (), []])
def test_nothing_named_means_every_channel(value: tuple[str, ...] | list[str] | None) -> None:
    assert ChannelFilter.parse(value) is None


def test_a_single_name_includes_only_that_channel() -> None:
    channel_filter = ChannelFilter.parse("security")

    assert channel_filter is not None
    assert channel_filter.accepts("security")
    assert not channel_filter.accepts("app")


def test_bang_names_exclude_those_channels() -> None:
    channel_filter = ChannelFilter.parse(["!event", "!doctrine"])

    assert channel_filter is not None
    assert channel_filter.channels == frozenset({"event", "doctrine"})
    assert not channel_filter.accepts("event")
    assert channel_filter.accepts("app")


def test_mixing_both_forms_is_refused() -> None:
    with pytest.raises(MixedChannelFilterError) as raised:
        _ = ChannelFilter.parse(["app", "!event"])

    assert raised.value.channels == ("app", "!event")
