"""The HTTP methods a route marker applies to, normalised as markers read them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["normalized_methods"]


def normalized_methods(methods: str | Sequence[str]) -> tuple[str, ...]:
    """Upper-case ``methods`` and extend ``GET`` with ``HEAD``.

    A marker that names no method applies to every one; a marker that names
    ``GET`` also answers a ``HEAD`` request for the same resource — reading
    what a route would send is the same claim the route itself makes.
    """
    listed: Sequence[str] = (methods,) if isinstance(methods, str) else methods
    normalized = tuple(method.upper() for method in listed)
    if "GET" in normalized and "HEAD" not in normalized:
        return (*normalized, "HEAD")
    return normalized
