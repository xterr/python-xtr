"""The paths an application has mounted, by the endpoint function answering at them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.routing import iter_route_contexts

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.routing import BaseRoute

__all__ = ["paths_by_endpoint"]


def paths_by_endpoint(routes: Sequence[BaseRoute]) -> dict[object, str]:
    """Return the effective path of every mounted route, keyed by its endpoint.

    The framework keeps a router included under a prefix as a wrapper, and
    offers the effective view of every route — prefixes applied — through
    ``iter_route_contexts``. Walked in reverse, so the first route of an
    endpoint mounted at two paths wins.
    """
    paths: dict[object, str] = {}
    for context in reversed(list(iter_route_contexts(routes))):
        if context.endpoint is not None and context.path is not None:
            paths[context.endpoint] = context.path
    return paths
