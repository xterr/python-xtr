"""Scheduling: the shop's schedule and its tasks.

``bookshop debug:scheduler`` lists what runs next; ``bookshop messenger:consume
scheduler_default -vv`` runs it — the scheduler bundle registers that transport, nothing in
the messenger config names it. In dev a heartbeat runs every two seconds, so a short
``--time-limit`` shows the schedule working.

Tasks — a class, methods of a class, and functions — run without writing a message. Each run
sends a ``ServiceCallMessage`` naming the target; the scheduler's handler calls it. The
container builds a task class with its dependencies, and a function task asks for services
with a marker, as any container-called function does.

=================================  ============================  ==========================
Target                             Trigger                       Where
=================================  ============================  ==========================
``heartbeat``                      every 2 s — dev and test      the scheduler's worker
``CatalogReport.build``            every 10 minutes, jittered    the scheduler's worker
``Housekeeping.forget_queries``    ``#daily``                    the scheduler's worker
``Housekeeping.reindex``           ``#weekly``, argument         the scheduler's worker
``purge_abandoned_carts``          03:00 Bucharest — prod only   sent to ``jobs``
=================================  ============================  ==========================

The schedule's own message is in ``bookshop.message.restock_check``, its handler in
``bookshop.message_handler.check_restock_handler``, and who hears about each run in
``bookshop.event_listener``.
"""

from __future__ import annotations

__all__: list[str] = []
