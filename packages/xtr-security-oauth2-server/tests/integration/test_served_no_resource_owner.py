"""The authorization endpoint reached with nobody authenticated on the request.

A deployment whose firewall does not claim ``/authorize`` gets the request
through to the endpoint with no resource owner on it. There is then nobody to
ask for consent, and the endpoint has to refuse — delivered to the client's
redirect URI, echoing the state the client sent, and saying nothing about how
this deployment is put together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qsl, urlsplit

import pytest
from fastapi import FastAPI
from xtr_security_http.firewall.firewall import Firewall

from tests.support.served import (
    CLIENT_ID,
    REDIRECT_URI,
    SEED_PATH,
    json_of,
    oauth2_kernel,
    served_application,
    serving,
    text_field,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

pytestmark = pytest.mark.anyio

#: What ties the redirect back to the browser that started the flow.
STATE: Final = "the-state-a-refusal-has-to-echo"


def _application() -> FastAPI:
    """Return the deployment whose firewall leaves ``/authorize`` unclaimed."""
    return served_application(
        oauth2_kernel("tests.fixtures.oauth2_no_owner_app"),
        dependencies=[Firewall()],
    )


def _delivered(response: httpx.Response) -> Mapping[str, str]:
    """Return the parameters the refusal was delivered in."""
    return dict(parse_qsl(urlsplit(response.headers["location"]).query))


async def _authorize(client: httpx.AsyncClient, redirect_uri: str = REDIRECT_URI) -> httpx.Response:
    """Ask for a code with nobody authenticated on the request."""
    seeded = await client.post(SEED_PATH, params={"grant": "", "redirect_uri": REDIRECT_URI})
    assert seeded.status_code == 200, seeded.text
    query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "state": STATE,
    }
    if redirect_uri:
        query["redirect_uri"] = redirect_uri

    return await client.get("/authorize", params=query)


async def test_nobody_to_ask_is_refused_to_the_clients_redirect_uri() -> None:
    async with serving(_application()) as client:
        answered = await _authorize(client)

    assert answered.status_code == 302
    assert answered.headers["location"].startswith(REDIRECT_URI)
    assert _delivered(answered)["error"] == "access_denied"


async def test_the_refusal_echoes_the_state_the_client_sent() -> None:
    # RFC 6749 4.1.2.1: an error response carries the state exactly as a
    # successful one does, or a client cannot tell it from a forged redirect.
    async with serving(_application()) as client:
        answered = await _authorize(client)

    assert _delivered(answered)["state"] == STATE


async def test_the_client_is_not_told_how_the_deployment_is_put_together() -> None:
    async with serving(_application()) as client:
        answered = await _authorize(client)

    delivered = _delivered(answered)
    assert "nobody to ask for consent" in delivered["hint"]
    assert "firewall" not in delivered["hint"]


async def test_a_request_naming_no_redirect_uri_is_refused_as_a_document() -> None:
    # Nowhere safe to send it: the client named no redirect URI and the
    # registration holds more than nothing to choose from only by luck.
    async with serving(_application()) as client:
        answered = await _authorize(client, redirect_uri="")

    assert answered.status_code == 401
    refused = json_of(answered)
    assert text_field(refused, "error") == "access_denied"
    assert "firewall" not in text_field(refused, "hint")
