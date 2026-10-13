"""Where an answer points, and whether following it stays where it started."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import httpx

__all__ = ["next_hop", "same_origin"]


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
