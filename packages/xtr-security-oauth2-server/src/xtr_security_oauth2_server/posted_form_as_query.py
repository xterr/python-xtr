"""Reading an authorization request a browser posted as a form.

The protocol library reads an authorization request out of the query string,
the way a browser following a redirect sends one. A client may as well have
the browser post it, the parameters serialized as a form, and the
authorization endpoint answers both. Rather than teach every grant a second
place to look, a posted request is handed on with its form as its query, so a
grant, and every step reading the request before the endpoint does, reads one
request whichever way it came.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import urlencode

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["posted_form_as_query"]

#: The method a form travels as, spelt as it is on the wire: method names
#: are matched case-sensitively.
_POST: Final = "POST"

#: The one encoding an authorization request may be posted in.
_FORM_CONTENT_TYPE: Final = "application/x-www-form-urlencoded"

#: The parameter every authorization request names, and so the one telling
#: where the request was sent.
_RESPONSE_TYPE: Final = "response_type"

_NOT_A_FORM: Final = (
    f"Post an authorization request as an {_FORM_CONTENT_TYPE} form, or send it as a GET"
)

_SENT_TWICE: Final = (
    "Send the authorization request's parameters either in the query string or in a "
    "posted form, never in both"
)


async def posted_form_as_query(request: ServerRequestInterface) -> ServerRequestInterface:
    """Return ``request`` with the authorization request it carries in its query.

    Where the parameters are read from:

    - anything but a ``POST`` is read from its query, as it arrived;
    - a ``POST`` whose query names ``response_type`` is read from that query,
      as it arrived — a consent page's form posting the original query back,
      the owner's answer in its body;
    - any other ``POST`` is read from its body, which must be a form; the
      form becomes the request's query parameters and its query string.

    One request is never read from two places: a ``POST`` carrying the request
    in its form is refused if its query string is non-empty, and a ``POST``
    whose query names ``response_type`` is refused if its body names it too,
    since the server would otherwise have to pick which of two values sent
    under one name it was asked for. The consent form's own fields are not the
    request, so they may travel beside the query it posts back.

    The body is read before the form is asked for, which is the order a
    request still connected to the wire needs.

    Raises:
        OAuthServerError: ``invalid_request`` when a request read from its
            body is no form, or when its parameters are sent both in the
            query and in the body.
    """
    if request.get_method() != _POST:
        return request
    query = request.get_query_params()
    form = await _form_of(request)
    if _RESPONSE_TYPE in query:
        if form is not None and _RESPONSE_TYPE in form:
            raise OAuthServerError.invalid_request(_RESPONSE_TYPE, _SENT_TWICE)
        return request
    if form is None:
        raise OAuthServerError.invalid_request("Content-Type", _NOT_A_FORM)
    if query:
        raise OAuthServerError.invalid_request(_RESPONSE_TYPE, _SENT_TWICE)
    uri = request.get_uri().with_query(urlencode(_fields_of(form)))

    return request.with_uri(uri, preserve_host=True).with_query_params(form)


async def _form_of(request: ServerRequestInterface) -> Mapping[str, object] | None:
    """Return the form ``request`` posted, or ``None`` when its body is no form.

    A form with no fields is still a form, and reads as an empty one.
    """
    content_type = request.get_header_line("Content-Type")
    if content_type.partition(";")[0].strip().lower() != _FORM_CONTENT_TYPE:
        return None
    _ = await request.get_body().get_contents()
    parsed = request.get_parsed_body()
    if not isinstance(parsed, Mapping):
        return {}

    # The cast says what narrowing cannot: a mapping of anything is a mapping
    # of objects.
    return cast("Mapping[str, object]", parsed)


def _fields_of(form: Mapping[str, object]) -> list[tuple[str, object]]:
    """Return every field ``form`` carries, a repeated name once per value sent."""
    getlist = getattr(form, "getlist", None)
    if not callable(getlist):
        return list(form.items())

    return [(name, value) for name in form for value in cast("list[object]", getlist(name))]
