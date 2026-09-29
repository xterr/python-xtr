"""The moto stand-in fixture yields an endpoint a client can actually reach."""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request

import pytest

pytestmark = pytest.mark.anyio


def _reach(url: str) -> int:
    """Return the status a bare request to ``url`` gets, HTTP error or not.

    Any HTTP status proves the endpoint answered; only a failure to connect
    would raise something this does not turn into a number.
    """
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310  # pyright: ignore[reportAny] -- the url is the fixture's own loopback endpoint; the standard library types a response as Any
            return int(response.status)  # pyright: ignore[reportAny] -- the standard library types a response as Any
    except urllib.error.HTTPError as error:
        return int(error.code)


async def test_the_endpoint_is_reachable(moto_endpoint: str) -> None:
    assert moto_endpoint.startswith("http://127.0.0.1:")

    status = await asyncio.to_thread(_reach, moto_endpoint)

    assert status > 0
