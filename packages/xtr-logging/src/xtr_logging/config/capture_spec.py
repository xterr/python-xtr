"""Capturing the standard library's logging, as configuration.

Libraries an application depends on — an HTTP client, a database driver, a web
server — log through :mod:`logging`. A ``capture`` section sends all of it
into channels instead, and makes the channels the only output: nothing the
standard library would have printed is printed by it as well::

    [capture]
    level = "warning"

    [capture.loggers]
    httpx = "info"
    "sqlalchemy.engine" = { level = "warning", channel = "db" }
"""

from __future__ import annotations

import msgspec

from xtr_logging.level import Level

__all__ = ["CaptureSpec", "CapturedLoggerSpec"]


class CapturedLoggerSpec(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """How one standard logger, and the loggers below it, are captured.

    Attributes:
        level: The least severe record the standard logger lets through.
        channel: The channel its records arrive on; the capture's own channel
            when omitted.
    """

    level: Level | str = Level.WARNING
    channel: str | None = None

    def __post_init__(self) -> None:
        """Check the level as it is written.

        Raises:
            InvalidLevelError: If it names no level.
        """
        _ = Level.parse(self.level)


class CaptureSpec(msgspec.Struct, frozen=True, kw_only=True, forbid_unknown_fields=True):
    """Send every standard-library record into channels, and only there.

    Attributes:
        level: The threshold for every standard logger ``loggers`` says
            nothing about.
        channel: The channel captured records arrive on; the configuration's
            default channel when omitted.
        loggers: Standard loggers by name, each with a level — ``"info"`` —
            or with a level and a channel of their own. A name covers the
            loggers below it: ``httpx`` catches ``httpx._client``.
    """

    level: Level | str = Level.WARNING
    channel: str | None = None
    loggers: dict[str, CapturedLoggerSpec | Level | str] = msgspec.field(default_factory=dict)

    def __post_init__(self) -> None:
        """Check every level as it is written.

        Raises:
            InvalidLevelError: If a level names no level.
        """
        _ = Level.parse(self.level)
        for entry in self.loggers.values():
            if not isinstance(entry, CapturedLoggerSpec):
                _ = Level.parse(entry)

    def logger_spec(self, name: str) -> CapturedLoggerSpec:
        """The entry for ``name``, with a bare level read as a spec of its own."""
        entry = self.loggers[name]
        return entry if isinstance(entry, CapturedLoggerSpec) else CapturedLoggerSpec(level=entry)

    @property
    def channels(self) -> tuple[str, ...]:
        """Every channel the section names."""
        named = [self.channel] if self.channel is not None else []
        named.extend(
            spec.channel for spec in map(self.logger_spec, self.loggers) if spec.channel is not None
        )
        return tuple(named)
