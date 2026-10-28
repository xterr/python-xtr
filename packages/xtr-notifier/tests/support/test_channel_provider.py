from __future__ import annotations

import pytest
from xtr_service_contracts import ServiceProviderInterface

from tests.support.channel_provider import ChannelProvider
from tests.support.recording_channel import RecordingChannel
from xtr_notifier.channel import ChannelInterface


def test_it_is_a_service_provider_naming_its_channels() -> None:
    provider = ChannelProvider({"chat": RecordingChannel()})

    assert isinstance(provider, ServiceProviderInterface)
    assert provider.has("chat")
    assert not provider.has("sms")
    assert dict(provider.provided_services()) == {"chat": ChannelInterface}


@pytest.mark.anyio
async def test_it_hands_out_a_channel_and_records_the_name() -> None:
    channel = RecordingChannel()
    provider = ChannelProvider({"chat": channel})

    assert await provider.get("chat") is channel
    assert provider.built == ["chat"]
