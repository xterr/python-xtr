"""A small HTTP front on the same kernel — standard library only, no web framework.

It shows what a framework integration needs from the kernel, and nothing more:

- ``kernel.build()`` compiles the container before the server exists;
- ``compiled.lifespan(app)`` boots on enter and shuts down on exit — the hook a web
  framework's lifespan takes;
- each route is bound once, at startup, with ``bind_callable(container, route,
  per_call_scope=True)``: a route asking for something the container cannot provide fails at
  startup, and every request gets a scope of its own, so scoped services (the cart, the unit
  of work) live exactly one request;
- ``ServicesResetter.reset()`` after every request, as a worker does after every message.

A real framework replaces ``server.py``; the routes and the kernel stay as they are.
"""

from __future__ import annotations

__all__: list[str] = []
