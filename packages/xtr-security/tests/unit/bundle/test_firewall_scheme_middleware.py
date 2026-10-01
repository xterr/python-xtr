"""The scheme middleware activates a kernel's registry for a request's span."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_http import FirewallSchemeRegistry

from xtr_security.bundle._firewall_scheme_middleware import FirewallSchemeMiddleware

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

pytestmark = pytest.mark.anyio


async def test_the_middleware_activates_the_registry_around_the_request() -> None:
    from fastapi.security import HTTPBearer
    from xtr_security_http.firewall_scheme import FirewallScheme

    registry = FirewallSchemeRegistry()
    registry.register("api", HTTPBearer().model, scheme_name="api")
    seen: list[str] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send
        seen.append(FirewallScheme("api").scheme_name)

    middleware = FirewallSchemeMiddleware(downstream, registry)
    await middleware({"type": "http"}, _receive, _send)

    assert seen == ["api"]


async def _receive() -> dict[str, object]:
    return {"type": "http.request"}


async def _send(message: object) -> None:
    del message
