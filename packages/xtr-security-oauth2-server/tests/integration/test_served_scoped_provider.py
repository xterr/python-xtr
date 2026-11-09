"""A firewall reading this server's tokens loads their owners through a provider of the request."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from xtr_dependency_injection import Injected
from xtr_security import Security

from tests.fixtures.oauth2_scoped_provider_app.config import USER_IDENTIFIER, USER_PASSWORD
from tests.fixtures.oauth2_scoped_provider_app.services import LOADS
from tests.support.served import (
    CLIENT_ID,
    CLIENT_SECRET,
    SCOPE,
    json_of,
    oauth2_kernel,
    seed_any_grant_client,
    served_application,
    serving,
    text_field,
)

pytestmark = pytest.mark.anyio


def _api(app: FastAPI) -> None:
    """Mount one route behind the firewall that reads this server's tokens."""
    router = APIRouter(prefix="/api")

    @router.get("/me")
    async def me(security: Injected[Security]) -> dict[str, object]:
        token = security.get_token()
        assert token is not None

        return {"caller": token.get_user_identifier()}

    app.include_router(router)


async def test_each_request_loads_the_tokens_owner_through_its_own_provider() -> None:
    LOADS.clear()
    application = served_application(
        oauth2_kernel("tests.fixtures.oauth2_scoped_provider_app"), _api
    )
    async with serving(application) as client:
        await seed_any_grant_client(client)
        issued = await client.post(
            "/token",
            data={
                "grant_type": "password",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": USER_IDENTIFIER,
                "password": USER_PASSWORD,
                "scope": SCOPE,
            },
        )
        headers = {"authorization": f"Bearer {text_field(json_of(issued), 'access_token')}"}
        first = await client.get("/api/me", headers=headers)
        second = await client.get("/api/me", headers=headers)

    assert first.status_code == second.status_code == 200
    assert json_of(first) == {"caller": USER_IDENTIFIER}
    assert [identifier for identifier, _ in LOADS] == [USER_IDENTIFIER, USER_IDENTIFIER]
    assert len({provider for _, provider in LOADS}) == 2
