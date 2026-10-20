from __future__ import annotations

import pytest

from xtr_notifier.channel import ChannelPolicy, ChannelPolicyInterface
from xtr_notifier.exception import InvalidArgumentError
from xtr_notifier.notification import Importance


def test_it_refuses_an_importance_it_does_not_define() -> None:
    policy = ChannelPolicy({"urgent": ["chat"]})

    with pytest.raises(InvalidArgumentError) as caught:
        _ = policy.get_channels(Importance.LOW)

    assert str(caught.value) == 'Importance "low" is not defined in the Policy.'


@pytest.mark.parametrize(
    "channels",
    [["chat"], ["chat", "sms"], ["chat", "chat/slack", "sms"]],
)
def test_it_returns_the_channels_of_an_importance(channels: list[str]) -> None:
    policy = ChannelPolicy({"urgent": channels})

    assert isinstance(policy, ChannelPolicyInterface)
    assert policy.get_channels(Importance.URGENT) == tuple(channels)


def test_it_keeps_its_own_copy_of_the_configuration() -> None:
    configured = {"urgent": ["chat"]}
    policy = ChannelPolicy(configured)

    configured["urgent"].append("sms")

    assert policy.get_channels(Importance.URGENT) == ("chat",)
