"""Which channels a handler serves: ``channels: [foo]`` or ``['!foo']``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from xtr_logging.exception.mixed_channel_filter_error import MixedChannelFilterError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ChannelFilter"]

_EXCLUDE: Final = "!"


@dataclass(frozen=True, slots=True)
class ChannelFilter:
    """Either "only these channels" or "every channel but these".

    Attributes:
        channels: The channels named, without their ``!``.
        exclusive: Whether the named channels are the ones left out.
    """

    channels: frozenset[str]
    exclusive: bool

    @classmethod
    def parse(cls, value: str | Sequence[str] | None) -> ChannelFilter | None:
        """Read a channel list as written in configuration.

        ``"foo"`` and ``["foo", "bar"]`` include; ``"!foo"`` and
        ``["!foo", "!bar"]`` exclude. ``None`` or an empty list means every
        channel, and returns ``None``.

        Raises:
            MixedChannelFilterError: If the list mixes both forms.
        """
        names = (value,) if isinstance(value, str) else tuple(value or ())
        if not names:
            return None
        excluded = [name.startswith(_EXCLUDE) for name in names]
        if any(excluded) and not all(excluded):
            raise MixedChannelFilterError(names)
        return cls(
            channels=frozenset(name.removeprefix(_EXCLUDE) for name in names),
            exclusive=all(excluded),
        )

    def accepts(self, channel: str) -> bool:
        """Whether a handler with this filter serves ``channel``."""
        return (channel in self.channels) is not self.exclusive
