"""Reading a submitted login form's fields, and validating each one.

The form-login authenticator's one delicate read: which parameter of the
request carries each field, and what a field must be to be a credential at
all. Kept here so the authenticator is the flow — the request it answers,
the passport it builds — and this is the reading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import BadCredentialsError

from xtr_security_http._request_parameters import payload_parameter, query_parameter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["form_login_credentials_of"]


def form_login_credentials_of(
    request: ServerRequestInterface,
    options: Mapping[str, object],
) -> tuple[str, str, str | None]:
    """Read the form's username, password and forgery token, validated.

    The cross-site request forgery field is read from the query string
    first, then the body; the username and the password from the body alone
    while the ``post_only`` option stands, from either place when it does
    not. The username is trimmed; every field must be a string, and the
    username and the password a non-empty one.

    Args:
        request: The request the form was submitted by.
        options: The form's field names and paths, keyed as the
            form-login authenticator's options are.

    Raises:
        BadCredentialsError: When a field is missing, empty or not a string
            at all — the form is answered, not the request rejected.
    """
    csrf_parameter = str(options["csrf_parameter"])
    csrf_token = _parameter_of(request, csrf_parameter)
    if csrf_token is not None and not isinstance(csrf_token, str):
        raise BadCredentialsError(f'The key "{csrf_parameter}" must be a string.')
    username_parameter = str(options["username_parameter"])
    password_parameter = str(options["password_parameter"])
    if options["post_only"]:
        username = payload_parameter(request, username_parameter)
        password = payload_parameter(request, password_parameter)
    else:
        username = _parameter_of(request, username_parameter)
        password = _parameter_of(request, password_parameter)
    if not isinstance(username, str):
        raise BadCredentialsError(f'The key "{username_parameter}" must be a string.')
    username = username.strip()
    if username == "":
        raise BadCredentialsError(f'The key "{username_parameter}" must be a non-empty string.')
    if not isinstance(password, str):
        raise BadCredentialsError(f'The key "{password_parameter}" must be a string.')
    if password == "":
        raise BadCredentialsError(f'The key "{password_parameter}" must be a non-empty string.')
    return username, password, csrf_token if isinstance(csrf_token, str) else None


def _parameter_of(request: ServerRequestInterface, name: str) -> object | None:
    """Read ``name`` out of the query string first, then the body."""
    asked = query_parameter(request, name)
    if asked is None:
        asked = payload_parameter(request, name)
    return asked
