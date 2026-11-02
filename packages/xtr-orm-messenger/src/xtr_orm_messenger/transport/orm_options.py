"""The settings an ``orm://`` transport reads from its configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from xtr_messenger import InvalidTransportOptionError
from xtr_messenger.transport.transport_options import (
    as_bool,
    as_float,
    as_int,
    reject_unknown_options,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["DEFAULT_QUEUE", "DEFAULT_TABLE_NAME", "ORM_OPTIONS", "ORM_SCHEME", "OrmOptions"]

ORM_SCHEME: Final = "orm"
"""The DSN scheme the transport serves."""

DEFAULT_TABLE_NAME: Final = "messenger_messages"
"""The table messages are kept in when the configuration names none."""

DEFAULT_QUEUE: Final = "default"
"""The queue a transport reads and writes when the configuration names none."""

ORM_OPTIONS: Final = (
    "auto_setup",
    "check_delayed_interval",
    "get_notify_timeout",
    "poll_interval",
    "queue",
    "redeliver_timeout",
    "table_name",
    "transactional",
    "use_notify",
)
"""Every setting an ``orm://`` transport accepts; any other is refused."""

_QUEUE_LENGTH: Final = 190
"""The width of the ``queue_name`` column, which indexes on every database at that size."""

_IDENTIFIER: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
"""A table name: a plain identifier, so it names one table and one notification channel."""


@dataclass(frozen=True, slots=True)
class OrmOptions:
    """How an ``orm://`` transport keeps, hands out and hands back its messages.

    Attributes:
        table_name: The table messages are kept in.
        queue: The queue this transport reads and writes; transports sharing a
            table but naming different queues never see each other's messages.
        redeliver_timeout: Seconds after which a message handed to a worker
            and never settled is handed out again — the worker is taken to have
            died with it.
        auto_setup: Create the table the first time an operation finds it
            missing.
        poll_interval: Seconds a worker waits before asking again when nothing
            was due.
        transactional: Write a message in the session of the unit of work
            under way, so it commits or rolls back with the handler's own
            changes; outside a unit it is written in a transaction of its own.
        use_notify: On PostgreSQL, wake a waiting worker the moment a message
            is sent instead of when its poll interval runs out.
        check_delayed_interval: Milliseconds a worker waiting for a
            notification waits at most before asking anyway — a delayed message
            falling due sends none.
        get_notify_timeout: Milliseconds one wait for a notification lasts at
            most.
    """

    table_name: str = DEFAULT_TABLE_NAME
    queue: str = DEFAULT_QUEUE
    redeliver_timeout: int = 3600
    auto_setup: bool = True
    poll_interval: float = 1.0
    transactional: bool = False
    use_notify: bool = True
    check_delayed_interval: int = 60_000
    get_notify_timeout: int = 60_000

    def __post_init__(self) -> None:
        """Refuse values the transport would misread.

        Raises:
            InvalidTransportOptionError: When a name is not a plain identifier,
                a queue is empty or too long for its column, or a duration is
                not positive.
        """
        if _IDENTIFIER.fullmatch(self.table_name) is None:
            raise InvalidTransportOptionError(
                "table_name", self.table_name, "a plain identifier: letters, digits and '_'"
            )
        if not 0 < len(self.queue) <= _QUEUE_LENGTH:
            raise InvalidTransportOptionError(
                "queue", self.queue, f"between 1 and {_QUEUE_LENGTH} characters"
            )
        if self.redeliver_timeout <= 0:
            raise InvalidTransportOptionError(
                "redeliver_timeout", str(self.redeliver_timeout), "a positive number of seconds"
            )
        if self.poll_interval <= 0:
            raise InvalidTransportOptionError(
                "poll_interval", str(self.poll_interval), "a positive number of seconds"
            )
        for name, value in (
            ("check_delayed_interval", self.check_delayed_interval),
            ("get_notify_timeout", self.get_notify_timeout),
        ):
            if value <= 0:
                raise InvalidTransportOptionError(
                    name, str(value), "a positive number of milliseconds"
                )

    @classmethod
    def from_settings(cls, settings: Mapping[str, str]) -> OrmOptions:
        """Read the options out of a transport's settings, the defaults filling the rest.

        Raises:
            UnknownTransportOptionError: If a setting is not one this transport
                accepts.
            InvalidTransportOptionError: If a value is not what its setting
                takes.
        """
        reject_unknown_options(ORM_SCHEME, settings, ORM_OPTIONS)
        base = cls()
        return cls(
            table_name=settings.get("table_name", base.table_name),
            queue=settings.get("queue", base.queue),
            redeliver_timeout=as_int(settings, "redeliver_timeout", base.redeliver_timeout),
            auto_setup=as_bool(settings, "auto_setup", base.auto_setup),
            poll_interval=as_float(settings, "poll_interval", base.poll_interval),
            transactional=as_bool(settings, "transactional", base.transactional),
            use_notify=as_bool(settings, "use_notify", base.use_notify),
            check_delayed_interval=as_int(
                settings, "check_delayed_interval", base.check_delayed_interval
            ),
            get_notify_timeout=as_int(settings, "get_notify_timeout", base.get_notify_timeout),
        )
