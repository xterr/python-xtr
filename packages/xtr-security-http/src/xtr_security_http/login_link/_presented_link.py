"""Reading the login link a request presents, parameter by parameter.

A followed link arrives as a URL — its parameters in the query string —
or as a form posting it, its parameters in the body. The reading here
walks the same places in the same order for every parameter, and refuses
the ones a link cannot be read without: the messages are the link's own
vocabulary, the same ones a minted link would have answered with.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http.exception import InvalidLoginLinkError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = [
    "PARAMETER_NAME",
    "extra_parameters_of",
    "request_parameter_of",
    "required_parameter_of",
]

#: A parameter name a link can carry: the characters a query string keeps
#: unescaped, so the name reads back the way it was written.
PARAMETER_NAME: Final = re.compile(r"^[A-Za-z0-9_.-]+$")


def request_parameter_of(request: ServerRequestInterface, name: str) -> object | None:
    """Read ``name`` out of the request the way a presented link is read.

    The query string first — a link is a URL, and its parameters travel
    there — then the body of a request that is not a ``GET`` or ``HEAD``,
    where a form posting the link carries them. A name the request
    repeats answers with the structure it arrived as, for the caller to
    narrow.
    """
    value = query_parameter(request, name)
    if value is not None:
        return value
    if request.get_method() not in ("GET", "HEAD"):
        return payload_parameter(request, name)
    return None


def required_parameter_of(
    request: ServerRequestInterface,
    name: str,
    *,
    digits: bool,
) -> str:
    """Read the parameter a presented link cannot be read without.

    Args:
        request: The request presenting the link.
        name: The parameter's name.
        digits: Whether the parameter must be a number, as the expiry is.

    Raises:
        InvalidLoginLinkError: When the parameter is missing, empty, not
            a string, or — for one that must be — not a number.
    """
    value = request_parameter_of(request, name)
    if value is None or value == "":
        raise InvalidLoginLinkError(f'Missing "{name}" parameter.')
    if not isinstance(value, str) or (digits and not value.isdigit()):
        raise InvalidLoginLinkError(f'Invalid "{name}" parameter.')
    return value


def extra_parameters_of(request: ServerRequestInterface) -> dict[str, str]:
    """Read the extra parameters a presented link's hash covers.

    Walks the names the link's ``hash_parameters`` lists, reading each
    from the request the same way the link's own parameters are read,
    and hands the mapping back with the list itself in it — the shape
    the hash was computed over, so it is the shape the check reads.

    Raises:
        InvalidLoginLinkError: When the list is not a string, a name it
            lists is malformed, or a value is missing or not a string.
    """
    parameters: dict[str, str] = {}
    names = request_parameter_of(request, "hash_parameters")
    if names is None:
        return parameters
    if not isinstance(names, str):
        raise InvalidLoginLinkError('Invalid "hash_parameters" parameter.')
    for name in names.split(","):
        if not PARAMETER_NAME.match(name):
            raise InvalidLoginLinkError(f'Invalid "{name}" parameter.')
        value = request_parameter_of(request, name)
        if value is None:
            raise InvalidLoginLinkError(f'Missing "{name}" parameter.')
        if not isinstance(value, str):
            raise InvalidLoginLinkError(f'Invalid "{name}" parameter.')
        parameters[name] = value
    parameters["hash_parameters"] = names
    return parameters
