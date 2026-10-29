"""A marker base whose subclasses are scoped, by ``@autoconfigure(lifetime=...)``."""

from __future__ import annotations

from xtr_dependency_injection import autoconfigure

__all__ = ["RequestScoped"]


@autoconfigure(lifetime="scoped", tags=["bookshop.request_scoped"])
class RequestScoped:
    """Every registered subclass lives for one scope: one command run, one web request.

    The rule sets the lifetime of every matching definition, so a subclass needs only
    ``@as_service`` — it cannot forget to be scoped.
    """
