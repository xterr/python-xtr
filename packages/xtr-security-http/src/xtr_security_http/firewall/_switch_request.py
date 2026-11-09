"""Reading the parameters a user switch is asked by."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast

from xtr_security_http._form_content_type import is_form_content_type
from xtr_security_http._request_parameters import (
    header_parameter,
    payload_parameter,
    query_parameter,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["request_parameter_of", "switch_username_of"]

_SAFE_METHODS = ("GET", "HEAD")

#: The one form encoding whose body is read to find a parameter: a urlencoded
#: form is a few fields, while a multipart one may carry files of any size.
_URLENCODED_FORM: Final = frozenset({"application/x-www-form-urlencoded"})


async def request_parameter_of(request: ServerRequestInterface, name: str) -> object | None:
    """Read ``name`` where a switch request carries it: the query string, then the body.

    The body is read only for a request that is not safe — one that may
    carry a submitted form — and only when it is a urlencoded form; the value
    comes back as it arrived, for the caller to narrow.

    These parameters are looked for on every request of a firewall that lets
    its users switch, so reading a multipart body here would read every upload
    into memory before its route runs. A multipart body is answered from what
    has parsed it already, if anything has, and is never read for it.
    """
    value = query_parameter(request, name)
    if value is not None or request.get_method() in _SAFE_METHODS:
        return value
    if is_form_content_type(request.get_header_line("Content-Type"), media_types=_URLENCODED_FORM):
        return await payload_parameter(request, name)
    return _parsed_parameter(request, name)


def _parsed_parameter(request: ServerRequestInterface, name: str) -> object | None:
    """Read ``name`` out of what the body has parsed into so far, reading nothing."""
    body = request.get_parsed_body()
    if not isinstance(body, Mapping):
        return None
    return cast("Mapping[str, object]", body).get(name)


async def switch_username_of(request: ServerRequestInterface, name: str) -> str | None:
    """Read the username a request asks to switch to, under ``name``.

    The query string first, then the body of a request that is not safe,
    then the header of the same name — a switch may be asked by any of
    the three. A value that is not text reads as no username at all: the
    local readers hand back what arrived, and a switch asked by anything
    but a name is not a switch this flow can carry out.
    """
    value = await request_parameter_of(request, name)
    if value is None or value == "":
        value = header_parameter(request, name)
    if not isinstance(value, str):
        return None
    return value
