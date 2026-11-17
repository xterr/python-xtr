"""The security panel, through the served fixture application with the profiler on and off."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import httpx
import pytest
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_http_kernel.profiler import FileProfilerStorage, Profile, Profiler

from tests.fixtures.security_app.bundles import BUNDLES
from xtr_security.data_collector import SecurityDataCollector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from pathlib import Path

pytestmark = pytest.mark.anyio

_APP = "tests.fixtures.security_app"
_PROFILER_ON = "tests.fixtures.profiler_on"


def _kernel(*resources: str) -> Kernel:
    return Kernel(
        _APP,
        env="test",
        debug=True,
        bundles=BUNDLES,
        resources=(_APP, *resources),
        concurrent_scoped_access=True,
    )


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PROFILER_TEST_FOLDER", str(tmp_path))
    return tmp_path


@pytest.fixture
async def client(folder: Path) -> AsyncIterator[httpx.AsyncClient]:
    """Serve the fixture's secured routes, profiled, inside the app's lifespan."""
    del folder
    app = FastAPI()

    @app.get("/api/me")
    async def me() -> dict[str, str]:
        return {"status": "me"}

    @app.get("/api/admin/panel")
    async def admin_panel() -> dict[str, str]:
        return {"status": "admin"}

    setup(app, _kernel(_PROFILER_ON))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as opened:
            yield opened


def _panel(folder: Path, response: httpx.Response) -> Mapping[str, object]:
    profile: Profile | None = FileProfilerStorage(folder).read(response.headers["x-debug-token"])
    assert profile is not None
    return profile.get_collector("security")


async def test_an_authenticated_request_keeps_the_firewall_the_token_and_the_grant(
    client: httpx.AsyncClient, folder: Path
) -> None:
    response = await client.get("/api/me", headers={"authorization": "Bearer good"})

    panel = _panel(folder, response)
    assert response.status_code == 200
    assert panel["enabled"] is True
    assert cast("Mapping[str, object]", panel["firewall"])["name"] == "api"
    token = cast("Mapping[str, object]", panel["token"])
    assert (token["user_identifier"], token["roles"], token["authenticated"]) == (
        "alice",
        ["ROLE_USER"],
        True,
    )
    (decision,) = cast("list[Mapping[str, object]]", panel["decisions"])
    assert (decision["attributes"], decision["result"]) == (["IS_AUTHENTICATED"], True)
    votes = [voter["vote"] for voter in cast("list[Mapping[str, object]]", decision["voters"])]
    assert "granted" in votes
    (authenticator,) = cast("list[Mapping[str, object]]", panel["authenticators"])
    # A bearer authenticator answers supports lazily: ``None``, a yes decided by authenticating.
    assert (authenticator["supports"], authenticator["authenticated"]) == (None, True)
    assert "AccessTokenAuthenticator" in cast("str", authenticator["authenticator"])
    assert "good" not in repr(panel)


async def test_a_denied_request_keeps_the_refusal_and_every_vote(
    client: httpx.AsyncClient, folder: Path
) -> None:
    response = await client.get("/api/admin/panel", headers={"authorization": "Bearer good"})

    panel = _panel(folder, response)
    assert response.status_code == 403
    (decision,) = cast("list[Mapping[str, object]]", panel["decisions"])
    assert (decision["attributes"], decision["result"]) == (["ROLE_ADMIN"], False)
    assert decision["strategy"] == "affirmative"
    voters = cast("list[Mapping[str, object]]", decision["voters"])
    assert [voter["vote"] for voter in voters if voter["vote"] != "abstain"] == ["denied"]
    assert panel["voter_strategy"] == "affirmative"


async def test_with_the_profiler_off_the_panel_is_not_registered() -> None:
    async with await _kernel().boot() as booted:
        assert not booted.container.has(SecurityDataCollector)
        assert not booted.container.has(Profiler)
