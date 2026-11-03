"""Following a redirect chain: where each answer points, and whether it stays where it began."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import httpx

__all__ = ["exchange", "next_hop", "same_origin"]


async def exchange(
    client: httpx.AsyncClient,
    outgoing: httpx.Request,
    auth: tuple[str, str] | None,
    max_redirects: int,
) -> tuple[httpx.Response, list[httpx.Response]]:
    """Send, then follow where each answer points until one points nowhere.

    Following is done here, a hop at a time, for the one thing the backend
    cannot be told: credentials belong to the host they were meant for, so an
    ``Authorization`` the backend dropped on the way out of that host is put
    back the moment the chain returns to it, and nowhere else.

    Args:
        client: The pool the request and every hop after it are sent through.
        outgoing: The request to send.
        auth: The user and password the first request authenticates with.
        max_redirects: How many hops may be followed.

    Returns:
        The last answer, and every answer before it, oldest first.
    """
    response = await client.send(outgoing, auth=auth, stream=True, follow_redirects=False)
    history: list[httpx.Response] = []
    origin = response.request.url
    authorization = cast("str | None", response.request.headers.get("authorization"))

    while len(history) < max_redirects:
        following = next_hop(response)
        if following is None:
            break

        if (
            authorization is not None
            and "authorization" not in following.headers
            and same_origin(following.url, origin)
        ):
            following.headers["Authorization"] = authorization

        history.append(response)
        await response.aclose()
        response = await client.send(following, stream=True, follow_redirects=False)

    return response, history


def next_hop(response: httpx.Response) -> httpx.Request | None:
    """Return the request that following ``response`` would make.

    Args:
        response: The answer to read a redirect off.

    Returns:
        The next request, or ``None`` when there is nowhere to go — either
        because the answer is not a redirect, or because where it points is
        not somewhere a request can be made to.
    """
    following = response.next_request
    if following is None:
        return None
    location = cast("str", response.headers.get("location", ""))
    if _names_no_host(location) or not following.url.host:
        return None

    return following


def same_origin(one: httpx.URL, other: httpx.URL) -> bool:
    """Tell whether two URLs name the same scheme, host and port.

    Args:
        one: A URL.
        other: The URL to compare it with.

    Returns:
        ``True`` when a connection to either would be a connection to the
        same place.
    """
    return (one.scheme, one.host, one.port) == (other.scheme, other.host, other.port)


def _names_no_host(location: str) -> bool:
    """Whether a Location names an authority and then leaves it empty.

    ``//?foo=bar`` says "another host, the same scheme" and names no host, so
    there is nowhere for it to point; a relative reference such as ``..``
    names no authority at all, which is not the same thing — it is resolved
    against the URL it arrived on.
    """
    if not location.startswith("//"):
        return False

    authority = location[2:]
    for delimiter in ("/", "?", "#"):
        authority = authority.partition(delimiter)[0]

    return authority == ""
