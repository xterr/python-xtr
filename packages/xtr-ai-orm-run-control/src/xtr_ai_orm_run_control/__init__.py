"""Cross-process status and cancellation of agent runs in a relational database, for xtr-ai.

:class:`OrmRunControl` keeps runs in one table, written through an xtr-orm
connection's engine in short transactions of its own, so a run started in one
process is read and cancelled from any other. :class:`RunMappingDriver` adds
the table to a connection's definitions, so ``orm:migrations:diff`` writes it.
"""

from __future__ import annotations

from .orm_run_control import OrmRunControl
from .run_mapping_driver import RunMappingDriver
from .run_table import DEFAULT_TABLE_PREFIX, run_table

__all__ = ["DEFAULT_TABLE_PREFIX", "OrmRunControl", "RunMappingDriver", "run_table"]
