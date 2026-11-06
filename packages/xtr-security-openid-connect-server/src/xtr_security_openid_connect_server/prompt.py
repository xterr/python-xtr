"""Reading the ``prompt`` a sign-in is asked with, and the refusals it can end in.

A client signing an end-user in says in ``prompt`` whether the server may show
them anything at all (``none``), must have them sign in again (``login``), or
must ask for their consent again (``consent``). :func:`parse_prompt` reads the
parameter. A sign-in that cannot be made the way it was asked for ends in one
of two refusals, each delivered to the client like any other:
:func:`login_required` when the end-user would have to sign in, and
:func:`consent_required` when they would have to be asked for consent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.redirect_uri import redirect_uri_carrying

if TYPE_CHECKING:
    from xtr_security_oauth2_server.event.authorization_request_resolve_event import (
        AuthorizationRequestResolveEvent,
    )

__all__ = ["consent_required", "login_required", "parse_prompt"]

#: The ``prompt`` values this server acts on.
_ACTED_ON: Final[frozenset[str]] = frozenset({"none", "login", "consent"})

#: The numbers the two refusals are catalogued under, following the
#: authorization server's own named errors, which take 2 to 15.
_CONSENT_REQUIRED_CODE: Final = 16
_LOGIN_REQUIRED_CODE: Final = 17

_UNKNOWN_VALUE: Final = (
    "Check the `prompt` parameter: it may carry `none`, `login` and `consent`, separated by spaces"
)
_NONE_BESIDE_ANOTHER: Final = (
    "Check the `prompt` parameter: `none` cannot be sent beside another value"
)


def parse_prompt(prompt: str | None) -> frozenset[str]:
    """Read the ``prompt`` an authorization request carried into the values it names.

    The parameter is a space-separated list, read as a set: a value repeated,
    or a space doubled, asks for nothing more. No parameter, or an empty one,
    asks for nothing.

    A value this server does not act on is refused rather than ignored: a
    client that asked for something and was not given it would carry on as
    though it had been. ``none`` beside any other value is refused too,
    because it forbids showing the end-user exactly what the other value asks
    to show them.

    Args:
        prompt: The ``prompt`` parameter as the request carried it, or
            ``None`` when it carried none.

    Raises:
        OAuthServerError: ``invalid_request`` when a value is not one this
            server acts on, or ``none`` comes beside another value.
    """
    if prompt is None:
        return frozenset()
    values = frozenset(value for value in prompt.split(" ") if value != "")
    if not values.issubset(_ACTED_ON):
        raise OAuthServerError.invalid_request("prompt", _UNKNOWN_VALUE)
    if "none" in values and len(values) > 1:
        raise OAuthServerError.invalid_request("prompt", _NONE_BESIDE_ANOTHER)

    return values


def consent_required(event: AuthorizationRequestResolveEvent) -> OAuthServerError:
    """Return the refusal a consent listener raises when it may not ask for consent.

    For a request that carried ``prompt=none`` and needs a consent the
    end-user has not given: the listener may not show a consent page, so it
    raises this instead, and the authorization endpoint delivers it to the
    client as it delivers any refusal.

    Args:
        event: The question the listener was asked, which names where the
            refusal goes and the state it carries back.
    """
    return OAuthServerError(
        "The authorization server requires end-user consent.",
        _CONSENT_REQUIRED_CODE,
        "consent_required",
        redirect_uri=_delivered_to(event.get_redirect_uri(), event.get_state()),
    )


def login_required(redirect_uri: str | None, state: str | None) -> OAuthServerError:
    """Return the refusal for a sign-in that cannot be made without the end-user signing in.

    For a request that carried ``prompt=none`` while nobody is signed in: the
    server may not show a login page, so it answers this instead.

    Args:
        redirect_uri: The validated redirect URI the request named, or
            ``None`` when it named none.
        state: The state the request carried, or ``None`` for none.
    """
    return OAuthServerError(
        "The authorization server requires end-user authentication.",
        _LOGIN_REQUIRED_CODE,
        "login_required",
        redirect_uri=_delivered_to(redirect_uri, state),
    )


def _delivered_to(redirect_uri: str | None, state: str | None) -> str | None:
    """Return where a refusal is delivered, carrying back the state the client sent.

    The state goes on the redirect as the authorization endpoint puts it there:
    a client that cannot tie an error to the request it made cannot tell it
    from a forged one. With no redirect URI there is nowhere to send the
    refusal, so it is answered as a document.
    """
    if redirect_uri is None:
        return None
    if state is None:
        return redirect_uri

    return redirect_uri_carrying(redirect_uri, {"state": state})
