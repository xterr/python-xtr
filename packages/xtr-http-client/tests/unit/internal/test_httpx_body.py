from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio
import anyio.lowlevel
import httpx
import pytest

from xtr_http_client.exception import TransportError, TransportTimeoutError
from xtr_http_client.internal.httpx_body import HttpxBody

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Self

pytestmark = pytest.mark.anyio

_REQUEST = httpx.Request("GET", "http://example.test/orders")


def _answer() -> httpx.Response:
    return httpx.Response(200, content=b"", request=_REQUEST)


async def _pieces(*parts: bytes) -> AsyncIterator[bytes]:
    for part in parts:
        await anyio.lowlevel.checkpoint()
        yield part


@final
class _Broken:
    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        raise httpx.ReadError("the connection went away")


async def test_a_body_iterates_over_itself() -> None:
    body = HttpxBody(_answer(), _pieces(b"one", b"two"))

    assert [piece async for piece in body] == [b"one", b"two"]


async def test_a_broken_transfer_is_reported_in_this_package_s_terms() -> None:
    body = HttpxBody(_answer(), _Broken())

    with pytest.raises(TransportError, match="the connection went away"):
        _ = await anext(body)


async def test_a_body_that_outlasts_the_deadline_is_a_timeout() -> None:
    body = HttpxBody(_answer(), _pieces(b"late"), anyio.current_time() - 1)

    with pytest.raises(TransportTimeoutError, match="Maximum duration reached"):
        _ = await anext(body)


async def test_a_body_given_no_deadline_waits_as_long_as_it_takes() -> None:
    body = HttpxBody(_answer(), _pieces(b"in time"))

    assert await anext(body) == b"in time"


async def test_closing_a_body_lets_go_of_the_transfer() -> None:
    response = _answer()
    body = HttpxBody(response, _pieces())

    await body.aclose()

    assert response.is_closed
