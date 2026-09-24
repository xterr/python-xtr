"""Trigger at a different level depending on which channel spoke."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_logging.level import Level

from .activation_strategy_interface import ActivationStrategyInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["ChannelLevelActivationStrategy"]


@final
class ChannelLevelActivationStrategy(ActivationStrategyInterface):
    """Releases the buffer on a level that varies by channel.

    One request touches many channels, and they do not all deserve the same
    alarm. Trigger on ``ERROR`` everywhere by default, say, but on ``WARNING``
    for a channel where a warning is already worth the whole log.
    """

    __slots__ = ("_by_channel", "_default")

    def __init__(
        self,
        default_action_level: LevelLike,
        channel_to_action_level: Mapping[str, LevelLike] | None = None,
    ) -> None:
        """Activate on ``default_action_level``, or a channel's own level where given.

        Raises:
            InvalidLevelError: If any level names no level.
        """
        self._default: Level = Level.parse(default_action_level)
        self._by_channel: dict[str, Level] = {
            channel: Level.parse(level)
            for channel, level in (channel_to_action_level or {}).items()
        }

    @override
    def is_handler_activated(self, record: LogRecord, /) -> bool:
        """Whether ``record`` reaches the level its channel activates on."""
        threshold = self._by_channel.get(record.channel, self._default)
        return record.level >= threshold
