"""The firewall runner is a no-op when no firewall claims the request."""

from __future__ import annotations

import pytest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager

from tests.support.requests import make_request
from xtr_security_http._runner import run_firewall
from xtr_security_http.firewall_map import FirewallMap

pytestmark = pytest.mark.anyio


async def test_it_does_nothing_when_no_firewall_matches() -> None:
    await run_firewall(
        None,
        make_request(),
        (),
        firewall_map=FirewallMap(()),
        token_storage=TokenStorage(),
        access_decision_manager=AccessDecisionManager([]),
    )
