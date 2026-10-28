"""Reading the parameters a user switch is asked by."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_http._request_parameters import (
    header_parameter,
    payload_parameter,
    query_parameter,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["request_parameter_of", "switch_username_of"]

_SAFE_METHODS = ("GET", "HEAD")


def request_parameter_of(request: ServerRequestInterface, name: str) -> object | None:
    """Read ``name`` where a switch request carries it: the query string, then the body.

    The body is read only for a request that is not safe — one that may
    carry a submitted form — and the value comes back as it arrived, for
    the caller to narrow.
    """
    value = query_parameter(request, name)
    if value is None and request.get_method() not in _SAFE_METHODS:
        value = payload_parameter(request, name)
    return value


def switch_username_of(request: ServerRequestInterface, name: str) -> str | None:
    """Read the username a request asks to switch to, under ``name``.

    The query string first, then the body of a request that is not safe,
    then the header of the same name — a switch may be asked by any of
    the three. A value that is not text reads as no username at all: the
    local readers hand back what arrived, and a switch asked by anything
    but a name is not a switch this flow can carry out.
    """
    value = request_parameter_of(request, name)
    if value is None or value == "":
        value = header_parameter(request, name)
    if not isinstance(value, str):
        return None
    return value
