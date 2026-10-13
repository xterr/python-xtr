"""An answer from the backend, read as the response this package hands back."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from xtr_http_message import Response

from xtr_http_client.internal.httpx_body import HttpxBody
from xtr_http_client.internal.httpx_redirect import next_hop
from xtr_http_client.internal.response_body import ResponseBody

from .http_response import HttpResponse

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import httpx

__all__ = ["to_http_response"]


@runtime_checkable
class _ConnectionInterface(Protocol):
    """The connection an answer came in on, as much of it as the record reads."""

    def get_extra_info(self, info: str) -> object:
        """Return what the connection knows under ``info``, or ``None``."""
        ...


async def to_http_response(  # noqa: PLR0913 — one call site, and every part arrives apart
    response: httpx.Response,
    history: Sequence[httpx.Response],
    method: str,
    start_time: float,
    user_data: object,
    *,
    deadline: float | None = None,
    decode: bool = True,
) -> HttpResponse:
    """Return the response for an answer whose head has arrived.

    The three parts of a response are assembled from three different places,
    which is why they are passed apart: the message is this answer's status
    line and headers, the body is still coming off this answer's transfer,
    and the info is the record of the whole chain that led here.

    Args:
        response: The last answer of the chain, its body unread.
        history: The answers before it, in the order they came, so the record
            can count the hops and keep every status line.
        method: The method of the last request made.
        start_time: When the request was sent, as a wall clock reading.
        user_data: What the caller asked to find again on the response.
        deadline: When the whole request runs out of time, on anyio's clock;
            the body is held to it as the head was. ``None`` is no limit.
        decode: Whether the body is to be handed over decoded. It is, unless
            the caller asked for an encoding outright — in which case what
            they asked for is what they get, as it arrived.

    Returns:
        The response, ready to be read.
    """
    message = Response(
        response.status_code,
        _headers(response),
        None,
        response.http_version.rpartition("/")[2],
        response.reason_phrase,
    )
    pieces = response.aiter_bytes() if decode else response.aiter_raw()
    body = ResponseBody(HttpxBody(response, pieces, deadline))

    return HttpResponse(
        message,
        body,
        _info(response, history, method, start_time, user_data),
        response.aclose,
    )


def _info(
    response: httpx.Response,
    history: Sequence[httpx.Response],
    method: str,
    start_time: float,
    user_data: object,
) -> dict[str, object]:
    """What the transfer knows about itself by the time its head is in."""
    info: dict[str, object] = {
        "canceled": False,
        "error": None,
        "http_code": response.status_code,
        "http_method": method,
        "redirect_count": len(history),
        "redirect_url": _redirect_url(response),
        "response_headers": _lines([*history, response]),
        "start_time": start_time,
        "total_time": time.time() - start_time,
        "url": _url(response),
        "user_data": user_data,
    }
    address = _primary_ip(response)
    if address is not None:
        info["primary_ip"] = address

    return info


def _headers(response: httpx.Response) -> dict[str, list[str]]:
    """Every header of an answer, in the case and the order it arrived in."""
    headers: dict[str, list[str]] = {}
    for raw_name, raw_value in response.headers.raw:
        name = raw_name.decode("latin-1")
        headers.setdefault(_first_cased(headers, name), []).append(raw_value.decode("latin-1"))

    return headers


def _first_cased(headers: dict[str, list[str]], name: str) -> str:
    """The case a header name was first seen in, so a repeat does not split it."""
    wanted = name.lower()
    for seen in headers:
        if seen.lower() == wanted:
            return seen

    return name


def _lines(chain: Sequence[httpx.Response]) -> list[str]:
    """The raw status and header lines of every hop, in the order they arrived."""
    lines: list[str] = []
    for answer in chain:
        lines.append(f"{answer.http_version} {answer.status_code} {answer.reason_phrase}")
        lines += [
            f"{name.decode('latin-1')}: {value.decode('latin-1')}"
            for name, value in answer.headers.raw
        ]

    return lines


def _redirect_url(response: httpx.Response) -> str | None:
    """Where the answer points, resolved, when nobody followed it."""
    following = next_hop(response)
    if following is None:
        return None

    return str(following.url)


def _url(response: httpx.Response) -> str:
    """The URL of the last hop, with an empty path written as the root it means."""
    url = response.url

    return str(url.copy_with(raw_path=url.raw_path))


def _primary_ip(response: httpx.Response) -> str | None:
    """The address the last hop was answered from, when the transfer knows it."""
    extensions = cast("Mapping[str, object]", response.extensions)
    connection = extensions.get("network_stream")
    if not isinstance(connection, _ConnectionInterface):
        return None

    address = connection.get_extra_info("server_addr")
    if not isinstance(address, tuple) or not address:
        return None
    first = cast("object", address[0])

    return first if isinstance(first, str) else None
