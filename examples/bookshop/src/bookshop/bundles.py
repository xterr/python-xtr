"""The root bundles, each mapped to the environments it is active in.

Installing a package activates nothing: a bundle is active because it is listed here, or
because an active bundle requires it with ``@required_bundle``. Run ``bookshop debug:bundles``
to see which is which — the ``Source`` column says ``listed`` or ``required``.

Flags: ``{"all": True}`` is every environment; an environment named explicitly wins over
``"all"``, so ``{"all": True, "prod": False}`` is everywhere but prod.

``xtr-recipes recipes:sync`` writes this file whole, so what an entry is for is recorded
here rather than in a comment beside it.

What each entry brings:

- ``OrmBundle`` — the database: engines, sessions per unit of work, migrations, and — with the
  messenger bundle active — the ``orm_*`` middleware the bus lists in ``config/messenger.py``.
- ``HttpKernelBundle`` — brings ``EventDispatcherBundle`` with it; the web entry point's
  request lifecycle.
- ``SchedulerBundle`` — brings ``MessengerBundle`` with it; with the cache bundle active it
  adds a ``"scheduler"`` pool.
- ``RateLimiterBundle`` — limits on routes, on outgoing mail, on anything; with the cache and
  lock bundles active its limiters keep their state in a ``"rate_limiter"`` pool it adds,
  under the default lock.
- ``JwtBundle`` — self-issued JSON Web Tokens: brings ``SecurityBundle`` with it (which in
  turn needs the event-dispatcher and http-kernel bundles, already active), and registers the
  jwt authenticator the api firewall lists. An add-on bundle: it fails the build unless
  ``config/jwt.py`` names a signing key, so it is not zero-config.
- ``DevToolsBundle`` — development helpers, never active in prod. Its resources are only
  scanned when active.

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
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_lock.bundle import LockBundle
from xtr_logging.bundle import LoggingBundle
from xtr_messenger.bundle import MessengerBundle
from xtr_orm.bundle import OrmBundle
from xtr_rate_limiter.bundle import RateLimiterBundle
from xtr_scheduler.bundle import SchedulerBundle
from xtr_security_jwt.bundle import JwtBundle

from bookshop.dev_tools import DevToolsBundle
from fulltext.bundle import FulltextBundle

__all__ = ["BUNDLES"]

BUNDLES = {
    LoggingBundle: {"all": True},
    ConsoleBundle: {"all": True},
    MessengerBundle: {"all": True},
    OrmBundle: {"all": True},
    DotenvBundle: {"all": True},
    FulltextBundle: {"all": True},
    EventDispatcherBundle: {"all": True},
    HttpKernelBundle: {"all": True},
    LockBundle: {"all": True},
    CacheBundle: {"all": True},
    SchedulerBundle: {"all": True},
    RateLimiterBundle: {"all": True},
    JwtBundle: {"all": True},
    DevToolsBundle: {"dev": True, "test": True},
}
