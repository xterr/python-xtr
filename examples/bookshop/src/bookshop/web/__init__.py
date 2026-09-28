"""The HTTP front on the same kernel: an application written as its framework documents it.

- ``routes.py`` — one router; path, query and body parameters in the signature, the services
  behind the same markers a command or a handler uses;
- ``app.py`` — the application, its exception handlers, and the single ``setup(app, kernel)``
  call that serves it from the kernel;
- ``__main__.py`` — the entry point behind ``uv run bookshop-web``.

``setup`` gives every application life a kernel of its own — built, booted and shut down with
the lifespan — and every request the scope its scoped services live in, so the cart and the
unit of work last exactly one request and are released once the response has gone out. Nothing
here resets services per request: that is a worker's answer to a message, not a request's.

The lifecycle around the endpoints comes from the ``http_kernel`` bundle listed in
:mod:`bookshop.bundles`: every response carries an ``X-Request-Id``, and an uncaught exception
is written to the ``request`` channel with the request that caused it.
"""

from __future__ import annotations

__all__: list[str] = []
