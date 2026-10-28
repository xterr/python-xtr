"""The request lifecycle: which application the router commands read.

Everything else is the bundle's default — every request is given a fresh ``X-Request-Id``,
echoed on the response, because an inbound one is not trusted unless the deployment says a
proxy sets it; an uncaught exception is written to the ``request`` channel (declared on the
logging config by the bundle itself). ``app`` is the one thing only the application knows:
``bookshop debug:router`` and ``bookshop router:match PATH`` import it from here, so neither
needs ``--app``.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_http_kernel.bundle import HttpKernelConfig

__all__ = ["http_kernel"]


@configure
def http_kernel() -> HttpKernelConfig:
    """Name the application the console reports on; nothing is imported until it does."""
    return HttpKernelConfig(app="bookshop.web.app:app")
