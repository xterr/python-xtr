"""Handlers that write somewhere, as configuration.

Each spec is inert data, told apart by its ``type`` — ``type: stream``.
Every value is checked as the spec is made, so a typo in a level fails
where it is written — or, for data parsed with
:meth:`~xtr_logging.config.logging_config.LoggingConfig.from_mapping`, with
the path to it.
"""

from __future__ import annotations

from typing import Literal

import msgspec
from typing_extensions import override

from xtr_logging.level import Level

from .channel_filter import ChannelFilter
from .formatter_specs import FormatterSpec  # noqa: TC001 — msgspec reads field types at runtime

__all__ = [
    "BaseHandlerSpec",
    "ConsoleHandlerSpec",
    "FormattedHandlerSpec",
    "NullHandlerSpec",
    "RotatingFileHandlerSpec",
    "ServiceHandlerSpec",
    "StdlibHandlerSpec",
    "StreamHandlerSpec",
    "SyslogHandlerSpec",
]


class BaseHandlerSpec(
    msgspec.Struct,
    frozen=True,
    kw_only=True,
    forbid_unknown_fields=True,
    tag_field="type",
):
    """What every handler entry accepts.

    Attributes:
        channels: Which channels the handler serves: ``"foo"``, ``["foo",
            "bar"]``, ``"!foo"`` or ``["!foo", "!bar"]``; every channel when
            omitted. Only applies to handlers on a channel's stack — one
            nested in another handler serves whatever its parent passes it.
        priority: Higher is consulted first; ties keep declaration order.
        nested: Keep the handler off every channel's stack, to be used only
            by the handler that names it. Implied for a handler another
            names.
        bubble: Whether a handled record goes on to the next handler.
    """

    channels: str | tuple[str, ...] | None = None
    priority: int = 0
    nested: bool = False
    bubble: bool = True

    def __post_init__(self) -> None:
        """Check the channel list as it is written.

        Raises:
            MixedChannelFilterError: If it mixes included and excluded channels.
        """
        _ = ChannelFilter.parse(self.channels)

    @property
    def channel_filter(self) -> ChannelFilter | None:
        """The parsed channel list, or ``None`` for every channel."""
        return ChannelFilter.parse(self.channels)

    @property
    def references(self) -> tuple[str, ...]:
        """The other handlers this one wraps, by name."""
        return ()


class _LevelledHandlerSpec(BaseHandlerSpec, frozen=True, kw_only=True):
    level: Level | str = Level.DEBUG

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        _ = Level.parse(self.level)


class FormattedHandlerSpec(_LevelledHandlerSpec, frozen=True, kw_only=True):
    """A handler that writes text, and so takes a level and a formatter."""

    formatter: FormatterSpec | str | None = None


class StreamHandlerSpec(FormattedHandlerSpec, frozen=True, kw_only=True, tag="stream"):
    """A :class:`~xtr_logging.handler.stream_handler.StreamHandler`.

    ``path`` is a file, or ``"stderr"`` / ``"stdout"`` — standard error by
    default, which suits a container that collects a process's output.
    """

    path: str = "stderr"
    file_permission: int | None = None


class RotatingFileHandlerSpec(FormattedHandlerSpec, frozen=True, kw_only=True, tag="rotating_file"):
    """A :class:`~xtr_logging.handler.rotating_file_handler.RotatingFileHandler`."""

    path: str
    max_files: int = 0
    date_format: str = "%Y-%m-%d"
    filename_format: str = "{filename}-{date}"
    file_permission: int | None = None


class SyslogHandlerSpec(FormattedHandlerSpec, frozen=True, kw_only=True, tag="syslog"):
    """A :class:`~xtr_logging.handler.syslog_handler.SyslogHandler`.

    ``address`` is ``host:port`` for UDP, or a socket path such as ``/dev/log``.
    """

    ident: str = "python"
    facility: str = "user"
    address: str = "localhost:514"


class ConsoleHandlerSpec(BaseHandlerSpec, frozen=True, kw_only=True, tag="console"):
    """A :class:`~xtr_logging.handler.console_handler.ConsoleHandler`.

    Its level follows the verbosity rather than being set;
    ``verbosity_levels`` overrides the map, keyed ``quiet``, ``normal``,
    ``verbose``, ``very_verbose`` and ``debug``.
    """

    stream: Literal["stderr", "stdout"] = "stderr"
    verbosity_levels: dict[str, Level | str] | None = None
    formatter: FormatterSpec | str | None = None

    @override
    def __post_init__(self) -> None:
        """Check the channel list and every mapped level."""
        super().__post_init__()
        for level in (self.verbosity_levels or {}).values():
            _ = Level.parse(level)


class NullHandlerSpec(_LevelledHandlerSpec, frozen=True, kw_only=True, tag="null"):
    """A :class:`~xtr_logging.handler.null_handler.NullHandler`."""


class StdlibHandlerSpec(_LevelledHandlerSpec, frozen=True, kw_only=True, tag="stdlib"):
    """A :class:`~xtr_logging.bridge.stdlib.stdlib_handler.StdlibHandler`.

    ``logger`` names the standard-library logger; the root logger by default.
    """

    logger: str = ""


class ServiceHandlerSpec(BaseHandlerSpec, frozen=True, kw_only=True, tag="service"):
    """A handler object supplied to the factory under ``id``."""

    id: str
