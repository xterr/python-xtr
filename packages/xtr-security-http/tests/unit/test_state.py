"""The request-state keys and the carried-response control-flow error."""

from __future__ import annotations

from starlette.responses import JSONResponse

from xtr_security_http._state import (
    AUTHENTICATED_FIREWALLS_KEY,
    FIREWALL_CONTEXT_KEY,
    TOKEN_KEY,
    CarriedResponse,
)


def test_the_keys_are_distinct_and_prefixed() -> None:
    keys = {AUTHENTICATED_FIREWALLS_KEY, FIREWALL_CONTEXT_KEY, TOKEN_KEY}

    assert len(keys) == 3
    assert all(key.startswith("_xtr_security_") for key in keys)


def test_a_carried_response_holds_its_response() -> None:
    response = JSONResponse({"ok": True})

    carried = CarriedResponse(response)

    assert carried.response is response
    assert isinstance(carried, Exception)
