"""The root bundles, each mapped to the environments it is active in.

Installing a package activates nothing: a bundle is active because it is listed here, or
because an active bundle requires it with ``@required_bundle``. Run ``bookshop debug:bundles``
to see which is which — the ``Source`` column says ``listed`` or ``required``.

Flags: ``{"all": True}`` is every environment; an environment named explicitly wins over
``"all"``, so ``{"all": True, "prod": False}`` is everywhere but prod.

Not listed, and active anyway:

- ``ClockBundle`` — required by ``LoggingBundle`` (softly) and ``FulltextBundle`` (hard).
- ``fulltext_metrics.bundle:MetricsBundle`` — required softly by ``FulltextBundle`` and not
  installed, so it is reported as skipped.
"""

from __future__ import annotations

from xtr_cache.bundle import CacheBundle
from xtr_console.bundle import ConsoleBundle
from xtr_dotenv.bundle import DotenvBundle
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_lock.bundle import LockBundle
from xtr_logging.bundle import LoggingBundle
from xtr_messenger.bundle import MessengerBundle
from xtr_scheduler.bundle import SchedulerBundle

from bookshop.dev_tools import DevToolsBundle
from fulltext.bundle import FulltextBundle

__all__ = ["BUNDLES"]

BUNDLES = {
    LoggingBundle: {"all": True},
    ConsoleBundle: {"all": True},
    MessengerBundle: {"all": True},
    DotenvBundle: {"all": True},
    FulltextBundle: {"all": True},
    EventDispatcherBundle: {"all": True},
    LockBundle: {"all": True},
    CacheBundle: {"all": True},
    # Brings MessengerBundle with it; with the cache bundle active it adds a "scheduler" pool.
    SchedulerBundle: {"all": True},
    # Development helpers: never active in prod. Its resources are only scanned when active.
    DevToolsBundle: {"dev": True, "test": True},
}
