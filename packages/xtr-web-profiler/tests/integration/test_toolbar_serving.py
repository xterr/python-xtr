"""The toolbar, drawn into a served application's pages — and only into the ones it should."""

from __future__ import annotations

import pytest

from tests.support.serving import PAGE, application, serving

pytestmark = pytest.mark.anyio


async def test_an_html_page_gets_the_toolbar_before_its_closing_body() -> None:
    async with serving(application()) as client:
        response = await client.get("/page")

    token = response.headers["x-debug-token"]
    body = response.text
    assert f'id="xtr-wdt-{token}"' in body
    assert body.index(f'id="xtr-wdt-{token}"') < body.rindex("</body>")
    assert body.startswith("<html><head><title>Shop</title></head><body><h1>Books</h1>")
    assert "content-length" not in response.headers or int(
        response.headers["content-length"]
    ) == len(response.content)


async def test_every_profiled_response_links_its_profile() -> None:
    async with serving(application()) as client:
        response = await client.get("/data")

    token = response.headers["x-debug-token"]
    assert response.headers["x-debug-token-link"] == f"http://shop.test/_profiler/{token}"
    assert response.json() == {"books": 3}


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/data", {}),
        ("/download", {}),
        ("/page", {"x-requested-with": "XMLHttpRequest"}),
        ("/page", {"sec-fetch-dest": "empty"}),
    ],
    ids=["json", "attachment", "xhr", "fetch"],
)
async def test_the_toolbar_is_not_drawn_into_what_a_browser_does_not_show_as_a_page(
    path: str, headers: dict[str, str]
) -> None:
    async with serving(application()) as client:
        response = await client.get(path, headers=headers)

    assert "x-debug-token" in response.headers
    assert "xtr-wdt-" not in response.text


async def test_a_redirect_is_left_alone_by_default() -> None:
    async with serving(application()) as client:
        response = await client.get("/away", headers={"accept": "text/html"})

    assert response.status_code == 302
    assert response.headers["location"] == "/page"
    assert "x-debug-token" in response.headers


async def test_an_intercepted_redirect_is_a_page_naming_where_it_leads() -> None:
    async with serving(application("intercepting")) as client:
        response = await client.get("/away", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert "location" not in response.headers
    assert 'href="/page"' in response.text
    assert f'id="xtr-wdt-{response.headers["x-debug-token"]}"' in response.text


async def test_a_background_request_asks_for_the_toolbar_to_reload_when_configured() -> None:
    async with serving(application("intercepting")) as client:
        replaced = await client.get("/data", headers={"x-requested-with": "XMLHttpRequest"})
    async with serving(application()) as client:
        plain = await client.get("/data", headers={"x-requested-with": "XMLHttpRequest"})

    assert replaced.headers["x-debug-toolbar-replace"] == "1"
    assert "x-debug-toolbar-replace" not in plain.headers


async def test_a_closing_tag_split_across_chunks_is_still_found() -> None:
    async with serving(application()) as client:
        response = await client.get("/stream")

    token = response.headers["x-debug-token"]
    assert response.text.startswith("<html><body><p>streamed</p>")
    assert response.text.endswith("</body></html>")
    assert f'id="xtr-wdt-{token}"' in response.text


async def test_a_page_with_a_policy_lets_the_toolbars_nonces_through() -> None:
    async with serving(application()) as client:
        response = await client.get("/protected")

    policy = response.headers["content-security-policy"]
    assert "script-src 'self' 'unsafe-inline' 'nonce-" in policy
    assert "style-src 'self' 'unsafe-inline' 'nonce-" in policy
    nonce = policy.split("'nonce-")[1].split("'")[0]
    assert f'nonce="{nonce}"' in response.text


async def test_what_is_drawn_carries_no_style_attribute_a_policy_would_block() -> None:
    # A nonce allows a <style> or <script> element, never a style="" attribute.
    async with serving(application()) as client:
        response = await client.get("/protected")

    assert 'style="' not in response.text
    assert "hidden" in response.text


async def test_the_profilers_own_pages_carry_no_policy_and_are_not_profiled() -> None:
    async with serving(application()) as client:
        response = await client.get("/_profiler/latest")

    assert "x-debug-token" not in response.headers
    assert "x-profiler-page" not in response.headers
    assert "xtr-wdt-" not in response.text


async def test_without_the_profiler_routes_a_response_says_so() -> None:
    async with serving(application(env="test")) as client:
        response = await client.get("/page")

    assert "x-debug-token" in response.headers
    assert response.headers["x-debug-error"] == "the profiler routes are not included"
    assert response.text == PAGE


async def test_a_compressing_application_still_gets_the_toolbar_on_its_pages() -> None:
    browser = {"accept": "text/html,application/xhtml+xml", "accept-encoding": "gzip"}
    async with serving(application(compress=True)) as client:
        page = await client.get("/page", headers=browser)
        data = await client.get("/data", headers={"accept-encoding": "gzip"})
        background = await client.get(
            "/page", headers={**browser, "x-requested-with": "XMLHttpRequest"}
        )
        json_only = await client.get(
            "/data", headers={"accept": "application/json", "accept-encoding": "gzip"}
        )
        anything = await client.get("/page", headers={"accept": "*/*", "accept-encoding": "gzip"})

    assert "content-encoding" not in page.headers
    assert f'id="xtr-wdt-{page.headers["x-debug-token"]}"' in page.text
    assert "content-encoding" not in data.headers
    assert background.headers["content-encoding"] == "gzip"
    assert json_only.headers["content-encoding"] == "gzip"
    assert "xtr-wdt-" in anything.text
