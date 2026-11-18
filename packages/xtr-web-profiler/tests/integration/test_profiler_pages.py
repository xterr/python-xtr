"""The profiler's pages, against profiles a served application really made."""

from __future__ import annotations

import pytest

from tests.support.serving import application, serving

pytestmark = pytest.mark.anyio

_PANELS = ("request", "time", "memory", "ajax", "exception", "logger", "events", "router", "config")


async def test_the_toolbar_fragment_holds_an_item_per_panel() -> None:
    async with serving(application()) as client:
        page = await client.get("/page")
        token = page.headers["x-debug-token"]
        fragment = await client.get(f"/_wdt/{token}")

    assert fragment.status_code == 200
    for name in ("request", "time", "memory", "ajax", "events", "router", "config"):
        assert f'data-xtr-panel="{name}"' in fragment.text
    assert "x-debug-token" not in fragment.headers


async def test_the_toolbar_of_an_unknown_profile_is_not_found() -> None:
    async with serving(application()) as client:
        missing = await client.get("/_wdt/ffffff")
        empty = await client.get("/_wdt/empty")

    assert missing.status_code == 404
    assert (empty.status_code, empty.text) == (200, "")


async def test_the_toolbar_stylesheet_may_be_cached() -> None:
    async with serving(application()) as client:
        response = await client.get("/_wdt/styles")

    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["cache-control"] == "max-age=600, private"
    assert ".xtr-wdt" in response.text


@pytest.mark.parametrize("panel", _PANELS)
async def test_every_panel_of_a_profile_renders(panel: str) -> None:
    async with serving(application()) as client:
        page = await client.get("/page?q=dune")
        token = page.headers["x-debug-token"]
        response = await client.get(f"/_profiler/{token}", params={"panel": panel})

    assert response.status_code == 200
    assert token in response.text
    assert "/page" in response.text


async def test_a_failed_request_opens_on_its_exception() -> None:
    async with serving(application("intercepting")) as client:
        failed = await client.get("/boom")
        latest = await client.get("/_profiler/latest")

    assert failed.status_code == 500
    assert latest.status_code == 200
    assert "the shelf collapsed" in latest.text
    assert "vscode://file/" in latest.text


async def test_an_unknown_profile_is_said_so() -> None:
    async with serving(application()) as client:
        response = await client.get("/_profiler/ffffff")

    assert response.status_code == 404
    assert "ffffff" in response.text


async def test_the_latest_profile_is_the_last_request() -> None:
    async with serving(application()) as client:
        _ = await client.get("/page")
        data = await client.get("/data")
        latest = await client.get("/_profiler/latest")

    assert data.headers["x-debug-token"] in latest.text


async def test_the_search_finds_profiles_and_a_token_goes_straight_to_its_profile() -> None:
    async with serving(application()) as client:
        page = await client.get("/page")
        token = page.headers["x-debug-token"]
        home = await client.get("/_profiler/")
        by_url = await client.get("/_profiler/search", params={"url": "/page", "limit": "5"})
        results = await client.get(by_url.headers["location"])
        by_token = await client.get("/_profiler/search", params={"token": token})
        bare = await client.get("/_profiler/search")

    assert home.status_code == 302
    assert home.headers["location"].endswith("/_profiler/empty/search/results")
    assert by_url.status_code == 302
    assert results.status_code == 200
    assert token in results.text
    assert by_token.headers["location"] == f"http://shop.test/_profiler/{token}"
    assert bare.headers["location"].endswith("/_profiler/empty/search/results")


async def test_the_source_view_shows_a_project_file_and_nothing_outside() -> None:
    async with serving(application()) as client:
        inside = await client.get("/_profiler/open", params={"file": __file__, "line": "3"})
        outside = await client.get("/_profiler/open", params={"file": "/etc/hosts"})
        climbing = await client.get("/_profiler/open", params={"file": "../../../etc/hosts"})
        hidden = await client.get("/_profiler/open", params={"file": ".env"})
        nothing = await client.get("/_profiler/open")

    assert inside.status_code == 200
    assert "xtr-line-3" in inside.text
    assert [outside.status_code, climbing.status_code, hidden.status_code, nothing.status_code] == [
        404,
        404,
        404,
        404,
    ]


async def test_with_profiling_turned_off_the_pages_are_not_found() -> None:
    async with serving(application("unprofiled")) as client:
        page = await client.get("/page")
        statuses = [
            (await client.get(path)).status_code
            for path in (
                "/_profiler/latest",
                "/_profiler/",
                "/_profiler/search",
                "/_profiler/empty/search/results",
                "/_profiler/open",
                "/_wdt/abc",
            )
        ]

    assert "x-debug-token" not in page.headers
    assert statuses == [404] * 6
