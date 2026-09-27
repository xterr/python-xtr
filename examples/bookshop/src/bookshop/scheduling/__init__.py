"""Scheduling: the shop's schedule, its tasks, and who hears about each run.

``bookshop debug:scheduler`` lists what runs next; ``bookshop messenger:consume
scheduler_default -vv`` runs it — the scheduler bundle registers that transport, nothing in
the messenger config names it. In dev a heartbeat runs every two seconds, so a short
``--time-limit`` shows the schedule working.
"""

from __future__ import annotations

__all__: list[str] = []
