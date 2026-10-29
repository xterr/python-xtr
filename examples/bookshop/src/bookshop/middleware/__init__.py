"""Middleware, three ways: named with ``@as_middleware``, and an instance in the config.

The configuration's ``middleware`` list names what runs, in order, ahead of routing and
handling. A name is resolved from the container — ``"logging"`` is the messenger bundle's,
``"audit_trail"`` and ``"timing"`` / ``"stopwatch"`` are declared here — and an object is
used as it is (see :class:`~bookshop.middleware.maintenance_guard_middleware.MaintenanceGuard`,
built in ``bookshop.config.packages.messenger``).

Middleware keeps no per-message state: one instance serves every dispatch, concurrently,
on the bus and in every worker.
"""

from __future__ import annotations

__all__: list[str] = []
