"""What an outgoing request is assembled from, before a connection is opened.

The request is authoritative and the options fill what it leaves out, so each
of its four parts — the URL, the headers, the body and the address the host is
reached at — is worked out from the two of them together. That is one decision
per part, made here, away from the exchange and the redirect chain that follow.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Mapping, Sequence
from typing import TYPE_CHECKING, Final, NamedTuple, cast

import httpx

from xtr_http_client.exception import InvalidArgumentError, TransportError

from .debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_http_message_contracts import RequestInterface

__all__ = [
    "Payload",
    "assemble_headers",
    "assemble_payload",
    "base_uri",
    "carries",
    "checked_body",
    "header_values",
    "pin_host",
    "target_url",
]

# Quoted by the contract rather than described, so it is written out once and
# never composed.
_BOTH_BODIES: Final = (
    'Define either the request body or the "body" or "json" option, setting both is not supported.'
)

# What a body of bytes, text or pieces is taken to be when nobody said: the
# only shape a request body has without a content type to read it by.
_FORM: Final = "application/x-www-form-urlencoded"

_NO_BODY: Final = (None, b"", "")


class Payload(NamedTuple):
    """The one body of a request, in whichever of three shapes it is to be sent."""

    content: bytes | str | AsyncIterator[bytes] | None
    form: Mapping[str, object] | None
    document: object


def target_url(request: RequestInterface, options: Mapping[str, object]) -> httpx.URL:
    """The URL to request: the request's own, resolved and with ``query`` merged in."""
    url = httpx.URL(str(request.get_uri()))

    base = options.get("base_uri")
    if url.is_relative_url and base is not None:
        url = httpx.URL(base_uri(base)).join(url)

    query = options.get("query")
    if query:
        url = url.copy_merge_params(cast("Mapping[str, str]", query))

    return url


def base_uri(base: object) -> str:
    """The URI a relative URL is resolved against.

    A sequence of them is for a client that retries, which moves along it
    from one attempt to the next; this one makes a single attempt, so it
    resolves against the first.
    """
    if isinstance(base, str):
        return base
    if isinstance(base, Sequence) and base:
        first = base[0]
        if isinstance(first, str):
            return first

    raise InvalidArgumentError(
        f'Option "base_uri" must be a URL or a list of them, "{debug_type(base)}" given.'
    )


def assemble_headers(
    request: RequestInterface,
    options: Mapping[str, object],
) -> list[tuple[str, str]]:
    """Every header to send: the request's, then the names it left out.

    The ``Host`` the request worked out from its own URI is dropped, because
    the URL actually requested may not be that one — a relative URI resolved
    against a base, or a host pinned to an address, both move it — and a
    header nobody asked for must not be the one that decides where a request
    lands. One the caller set by hand is kept and sent exactly as given.
    """
    headers = [
        (name, value)
        for name, values in request.get_headers().items()
        for value in values
        if not _is_implied_host(name, value, request)
    ]

    for name, value in _mapping(options.get("headers")).items():
        if carries(headers, name):
            continue
        headers += header_values(name, value)

    bearer = options.get("auth_bearer")
    if isinstance(bearer, str) and bearer and not carries(headers, "authorization"):
        headers.append(("Authorization", f"Bearer {bearer}"))

    return headers


def _is_implied_host(name: str, value: str, request: RequestInterface) -> bool:
    """Whether a header is the ``Host`` a request filled in from its own URI."""
    if name.lower() != "host":
        return False

    uri = request.get_uri()
    host = uri.get_host()
    port = uri.get_port()

    return value == (host if port is None else f"{host}:{port}")


async def assemble_payload(
    request: RequestInterface,
    options: Mapping[str, object],
    headers: list[tuple[str, str]],
) -> Payload:
    """What to send as the body, from the request or from the options, never both.

    A request carrying a body has already said what to send, so a ``body`` or
    ``json`` option alongside it is two answers to one question and is
    refused rather than one of them being picked.

    Raises:
        InvalidArgumentError: When the request carries a body and an option
            gives another.
    """
    carried = await request.get_body().get_contents()
    if carried:
        if options.get("body") not in _NO_BODY or options.get("json") is not None:
            raise InvalidArgumentError(_BOTH_BODIES)
        _imply_form(headers)

        return Payload(carried, None, None)

    return _asked_for(options, headers)


def _asked_for(options: Mapping[str, object], headers: list[tuple[str, str]]) -> Payload:
    """What the options alone say to send, for a request that carried no body.

    A mapping is a form, which the backend writes out; bytes, text and an
    iterable are a body nobody labelled, so they are said to be a form here;
    and a JSON document labels itself.
    """
    document = options.get("json")
    if document is not None:
        return Payload(None, None, document)

    body = options.get("body")
    if isinstance(body, Mapping):
        return Payload(None, cast("Mapping[str, object]", body), None)
    if isinstance(body, (bytes, str)) and body:
        _imply_form(headers)

        return Payload(body, None, None)
    if isinstance(body, AsyncIterable):
        _imply_form(headers)

        return Payload(checked_body(body), None, None)

    return Payload(None, None, None)


async def checked_body(source: AsyncIterable[object]) -> AsyncIterator[bytes]:
    """``source``, with a piece that is not bytes refused before it reaches the wire.

    Raises:
        TransportError: When the body produces anything other than bytes.
            The request fails rather than the backend tripping over it with
            an error from somewhere a caller cannot place.
    """
    async for piece in source:
        if not isinstance(piece, (bytes, bytearray)):
            raise TransportError(
                f'The request body produced "{debug_type(piece)}", which is not bytes.'
            )
        yield bytes(piece)


def pin_host(
    url: httpx.URL,
    options: Mapping[str, object],
    resolved: dict[str, str],
    headers: list[tuple[str, str]],
) -> tuple[httpx.URL, dict[str, str]]:
    """The URL to connect to, with the host swapped for the address it is pinned to.

    Pinning is what makes a request reach an address that has already been
    checked, so nothing can change under it between the check and the
    connection. The host survives the swap in two places that still need it:
    the ``Host`` header, which is what the server routes on, and the name the
    TLS handshake asks for.
    """
    resolved.update(_text_mapping(options.get("resolve")))

    host = url.raw_host.decode("ascii")
    address = resolved.get(host)
    if address is None:
        return url, {}

    _replace(headers, "Host", host if url.port is None else f"{host}:{url.port}")

    return url.copy_with(host=address), {"sni_hostname": host}


def carries(headers: Sequence[tuple[str, str]], name: str) -> bool:
    """Whether a header of that name is already there, matched without case."""
    wanted = name.lower()

    return any(present.lower() == wanted for present, _ in headers)


def header_values(name: str, value: object) -> list[tuple[str, str]]:
    """One header name and every value given for it."""
    if isinstance(value, str):
        return [(name, value)]
    if isinstance(value, Sequence):
        return [(name, str(one)) for one in value]

    raise InvalidArgumentError(
        f'Option "headers" must map a name to a string or a list of them, '
        f'"{debug_type(value)}" given for "{name}".'
    )


def _replace(headers: list[tuple[str, str]], name: str, value: str) -> None:
    """Make ``name`` hold ``value`` and nothing else."""
    wanted = name.lower()
    headers[:] = [entry for entry in headers if entry[0].lower() != wanted]
    headers.append((name, value))


def _imply_form(headers: list[tuple[str, str]]) -> None:
    """Say what an unlabelled body is, since a server cannot read one unlabelled."""
    if not carries(headers, "content-type"):
        headers.append(("Content-Type", _FORM))


def _mapping(value: object) -> Mapping[str, object]:
    """``value`` as a mapping, or an empty one when it was left out."""
    if isinstance(value, Mapping):
        return cast("Mapping[str, object]", value)

    return {}


def _text_mapping(value: object) -> dict[str, str]:
    """``value`` as a mapping of text to text, keeping only the entries that are."""
    return {name: entry for name, entry in _mapping(value).items() if isinstance(entry, str)}
