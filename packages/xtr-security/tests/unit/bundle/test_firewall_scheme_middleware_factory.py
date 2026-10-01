"""The scheme middleware factory wraps the application in the activating middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_http import FirewallSchemeRegistry

from xtr_security.bundle._firewall_scheme_middleware import FirewallSchemeMiddleware
from xtr_security.bundle._firewall_scheme_middleware_factory import (
    FirewallSchemeMiddlewareFactory,
)

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send

pytestmark = pytest.mark.anyio


async def test_the_factory_wraps_the_app() -> None:
    registry = FirewallSchemeRegistry()
    factory = FirewallSchemeMiddlewareFactory(registry)

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send

    wrapped = factory(downstream)

    assert isinstance(wrapped, FirewallSchemeMiddleware)
