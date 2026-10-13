"""The options a retrying client reads, rewrites and keeps to itself."""

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xtr_http_message_contracts import RequestInterface

__all__ = ["base_uri_rotation", "replays_body", "replays_request", "retries", "with_base_uri"]


def base_uri_rotation(value: object) -> tuple[str, ...] | None:
    """The base URIs an attempt moves along, or ``None`` when there is one URI.

    Args:
        value: What the ``base_uri`` option was given as.

    Returns:
        Every URI in order when several were named, or ``None`` when the
        option is one URI, or none, which is for the wrapped client to resolve
        against as it always does.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        return None

    return tuple(str(uri) for uri in value)


def with_base_uri(
    options: Mapping[str, object],
    base_uris: Sequence[str],
    attempt: int,
) -> dict[str, object]:
    """``options`` carrying the one base URI this attempt is to be made against.

    Moving along the list is what makes several base URIs worth naming: the
    first attempt goes to the first, the second to the second, and once the
    list runs out every further attempt stays on the last — the alternative
    being to come back to a URI that has already refused.

    Args:
        options: The options the request is being made with.
        base_uris: The URIs to move along, empty when none were named.
        attempt: How many attempts came before this one.

    Returns:
        The options to hand the wrapped client, whose ``base_uri`` is one URI
        or is gone — a list of them is this client's to walk, and means
        nothing to a client that sends one request.
    """
    sent = dict(options)
    if base_uris:
        sent["base_uri"] = base_uris[min(attempt, len(base_uris) - 1)]
    elif base_uri_rotation(sent.get("base_uri")) is not None:
        del sent["base_uri"]

    return sent


def retries(value: object, fallback: int) -> int:
    """How many times a request may be made again, as the option says or not.

    Args:
        value: What the ``max_retries`` option was given as.
        fallback: What the client was built with, used when the option says
            nothing.

    Returns:
        The number of retries allowed.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return fallback

    return value


def replays_body(options: Mapping[str, object]) -> bool:
    """Whether the body in ``options`` can be sent a second time.

    A body produced as it goes is gone once it has gone out: whatever
    produced it has been drained, and there is nothing left to send again. A
    request carrying one is made once, because a retry would send a request
    with no body at all rather than the request that failed.
    """
    return not isinstance(options.get("body"), AsyncIterable)


def replays_request(request: RequestInterface) -> bool:
    """Whether the body of ``request`` can be sent a second time.

    A stream that cannot be rewound has the same problem as a body produced
    as it goes: it has been read to its end by the attempt that failed.
    """
    body = request.get_body()

    return body.get_size() == 0 or body.is_seekable()
