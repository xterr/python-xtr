"""The paths an application has mounted, by the endpoint function answering at them."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import routing as fastapi_routing

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from starlette.routing import BaseRoute

__all__ = ["paths_by_endpoint"]


def paths_by_endpoint(routes: Sequence[BaseRoute]) -> dict[object, str]:
    """Return the effective path of every mounted route, keyed by its endpoint.

    Newer releases of the framework keep a router included under a prefix as a
    wrapper and offer the effective view of every route — prefixes applied —
    through ``iter_route_contexts``; older ones hold each route in the list
    directly. Both views carry the endpoint and the path, so one reading
    serves both. Walked in reverse, so the first route of an endpoint mounted
    at two paths wins.
    """
    iterate = cast(
        "Callable[[Sequence[BaseRoute]], Iterable[object]] | None",
        getattr(fastapi_routing, "iter_route_contexts", None),
    )
    contexts: Iterable[object] = iterate(routes) if iterate is not None else routes
    paths: dict[object, str] = {}
    for context in reversed(list(contexts)):
        endpoint = getattr(context, "endpoint", None)
        path = getattr(context, "path", None)
        if endpoint is not None and isinstance(path, str):
            paths[endpoint] = path
    return paths
