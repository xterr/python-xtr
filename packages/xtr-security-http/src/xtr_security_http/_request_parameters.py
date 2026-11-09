"""Reading a named parameter out of a request message.

The security layer keeps asking the same small question — which value did
the client send under this name, in the submitted form, in the query string,
in a header. A body parses into whatever its content type says it carries,
so the answer starts by narrowing: only a mapping carries named parameters,
and anything else reads as carrying none. Each reader hands back the value
as it arrived — narrowing it to text is the caller's, who knows what a
parameter means to it.

A request the server is still serving is born with its body unread, and its
parsed side answers only what a read of the body has yielded — so the body of
a submitted form is read before its fields are asked for. Only a form's: a
body of any other media type carries no named parameter to find, and reading
it would buffer an upload for nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from xtr_security_http._form_content_type import is_form_content_type

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["header_parameter", "payload_parameter", "query_parameter", "read_payload"]


async def read_payload(request: ServerRequestInterface) -> object | None:
    """Return what the request's body parsed into, reading a submitted form first.

    A served request fills its parsed side as its body is read, so a form's
    fields are there only once something has read it: the read comes first,
    and once the body is in the buffer it is a read of the buffer, the wire
    left alone. A body of any other media type is not read here, and what it
    parsed into — if anything has parsed it — is answered as it is.

    Args:
        request: The request whose body is read.

    Returns:
        Whatever parsing the body yielded, or ``None`` when nothing has been
        parsed into the request.
    """
    if is_form_content_type(request.get_header_line("Content-Type")):
        _ = await request.get_body().get_contents()
    return request.get_parsed_body()


async def payload_parameter(
    request: ServerRequestInterface,
    name: str,
    default: object | None = None,
) -> object | None:
    """Read ``name`` out of the parameters the request's body parsed into.

    A body is parsed into whatever its content type says it carries, so what
    comes back need not be named parameters at all — a JSON array, or
    nothing for a request with no body. Either reads as carrying no
    parameter, which is what a request that is not a form amounts to. The
    body is read first when it is a submitted form, the way
    :func:`read_payload` reads it.

    Args:
        request: The request whose body is read.
        name: The parameter name.
        default: What to answer with when the body carries no such name.

    Returns:
        The value under ``name``, or ``default``.
    """
    body = await read_payload(request)
    if not isinstance(body, Mapping):
        return default

    # The cast says what narrowing cannot: a mapping of anything is a mapping
    # of objects, and every value is then read as it arrived.
    return cast("Mapping[str, object]", body).get(name, default)


def query_parameter(
    request: ServerRequestInterface,
    name: str,
    default: object | None = None,
) -> object | None:
    """Read ``name`` out of the request's query string.

    A name the query repeats or nests answers with the structure it arrived
    as — a list, a nested mapping — not its first value; the caller narrows
    what it reads, the same as for a payload parameter.

    Args:
        request: The request whose query string is read.
        name: The parameter name.
        default: What to answer with when the query carries no such name.

    Returns:
        The value under ``name``, or ``default``.
    """
    return request.get_query_params().get(name, default)


def header_parameter(
    request: ServerRequestInterface,
    name: str,
    default: str | None = None,
) -> str | None:
    """Read the ``name`` header's value, joined when the header repeats.

    A header the request does not carry answers as one carrying an empty
    value would — both read as no value, and ``default`` comes back — because
    a header set to nothing carries no parameter, the same way an absent form
    field does.

    Args:
        request: The request whose headers are read.
        name: The header name, in any case.
        default: What to answer with when the header carries no value.

    Returns:
        The header's values joined with commas, or ``default``.
    """
    value = request.get_header_line(name)
    return value if value != "" else default
