"""OpenID Connect Core 1.0, Section 12 — Using Refresh Tokens.

"Upon successful validation of the Refresh Token, the response body is the
Token Response of Section 3.1.3.3 except that it might not contain an
id_token." This provider issues none on a refresh: the refresh states no new
sign-in, so it has nothing to state. The refresh is made by the repository's
own protocol client, reaching the served provider live.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_cache import ArrayAdapter
from xtr_security_http.oauth2.client_authentication import NoClientAuthentication
from xtr_security_http.oidc import OidcClient, OidcDiscovery

from tests.support.relying_party_login import forwarding_client
from tests.support.served import CLIENT_ID, openid_kernel, served_application, serving, text_field
from tests.support.sign_in import signed_in
from tests.support.signing import ISSUER

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio


async def _refreshed() -> tuple[Mapping[str, object], Mapping[str, object]]:
    """Sign in, refresh with the refresh token, and return both token answers."""
    async with serving(served_application(openid_kernel())) as provider:
        issued = await signed_in(provider)
        client = forwarding_client(provider)
        protocol = OidcClient(
            client,
            OidcDiscovery(client, ArrayAdapter(), issuer=ISSUER),
            CLIENT_ID,
            NoClientAuthentication(),
        )
        refreshed = await protocol.refresh_token(text_field(issued, "refresh_token"))

    return issued, refreshed


async def test_a_refresh_is_answered_with_a_new_access_token() -> None:
    issued, refreshed = await _refreshed()

    assert text_field(refreshed, "access_token") != text_field(issued, "access_token")


async def test_a_refresh_is_answered_without_an_id_token() -> None:
    issued, refreshed = await _refreshed()

    assert "id_token" in issued
    assert "id_token" not in refreshed
