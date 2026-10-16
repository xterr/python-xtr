"""Reading a named parameter out of a request message.

The security layer keeps asking the same small question — which value did
the client send under this name, in the submitted form, in the query string,
in a header. A body parses into whatever its content type says it carries,
so the answer starts by narrowing: only a mapping carries named parameters,
and anything else reads as carrying none. Each reader hands back the value
as it arrived — narrowing it to text is the caller's, who knows what a
parameter means to it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["header_parameter", "payload_parameter", "query_parameter"]


def payload_parameter(
    request: ServerRequestInterface,
    name: str,
    default: object | None = None,
) -> object | None:
    """Read ``name`` out of the parameters the request's body parsed into.

    A body is parsed into whatever its content type says it carries, so what
    comes back need not be named parameters at all — a JSON array, or
    nothing for a request with no body. Either reads as carrying no
    parameter, which is what a request that is not a form amounts to.

    Args:
        request: The request whose body is read.
        name: The parameter name.
        default: What to answer with when the body carries no such name.

    Returns:
        The value under ``name``, or ``default``.
    """
    body = request.get_parsed_body()
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
