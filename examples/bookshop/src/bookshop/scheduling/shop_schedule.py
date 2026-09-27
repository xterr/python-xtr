"""The shop's schedule — the starter schedule of the xtr-scheduler README, grown a little.

Declared with ``@as_schedule()``: it provides the ``default`` schedule, and every
``@as_cron_task`` / ``@as_periodic_task`` not naming a schedule joins it
(``bookshop.scheduling.tasks``). Without this class those tasks would still run — in a
plain schedule with no saved state and no lock.

- ``stateful`` — progress lives in the ``scheduler`` cache pool the scheduler bundle adds
  when the cache bundle is active; files here, so a worker restarted later resumes.
- ``process_only_last_missed_run`` — after downtime, one run of each message, not all.
- ``lock`` — from the lock bundle's default resource (file locks): start two workers and
  only one sends.
"""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_cache_contracts import CacheInterface
from xtr_dependency_injection import Target
from xtr_lock import LockFactory
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import RedispatchMessage
from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule
from xtr_scheduler.event import PreRunEvent

from bookshop.messaging.messages import ReindexCatalog

from .messages import RestockCheck

__all__ = ["ShopSchedule"]


@final
@as_schedule()
class ShopSchedule(ScheduleProviderInterface):
    """The ``default`` schedule: its own messages, the declared tasks, state and a lock."""

    def __init__(
        self,
        cache: Annotated[CacheInterface, Target("scheduler")],
        locks: LockFactory,
        logger: Annotated[LoggerInterface, Target("scheduler")],
    ) -> None:
        """Build the schedule on the ``scheduler`` pool and a lock from the default resource."""
        self._logger = logger
        self._schedule: Schedule = (
            Schedule(
                # Handled by the worker consuming the schedule, at a minute hashed from
                # the message's string form.
                RecurringMessage.cron("#hourly", RestockCheck("every title")),
                # Sent on through routing: ReindexCatalog declares ``jobs``, RabbitMQ in
                # prod, so the reindex runs on that worker pool, not on the scheduler.
                RecurringMessage.every(
                    "1 day", RedispatchMessage(ReindexCatalog(reason="nightly reindex"))
                ).with_jitter(60),
            )
            .stateful(cache)
            .process_only_last_missed_run()
            .lock(locks.create_lock("scheduler-default"))
            .before(self._announce)
        )

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule

    def _announce(self, event: PreRunEvent) -> None:
        """A listener of this schedule only: note each run before it is handled."""
        self._logger.debug(
            "running {message}, due {due}",
            {"message": str(event.message), "due": event.context.triggered_at.isoformat()},
        )
