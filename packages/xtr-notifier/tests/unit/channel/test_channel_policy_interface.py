from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.channel import ChannelPolicyInterface

if TYPE_CHECKING:
    from xtr_notifier.notification import Importance


class _Policy:
    def get_channels(self, importance: Importance) -> tuple[str, ...]:
        return (importance.value,)


def test_anything_that_maps_an_importance_to_channels_is_a_policy() -> None:
    assert isinstance(_Policy(), ChannelPolicyInterface)
    assert not isinstance(object(), ChannelPolicyInterface)
