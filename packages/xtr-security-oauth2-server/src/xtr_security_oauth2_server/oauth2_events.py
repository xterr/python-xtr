"""The names the bundle layer announces its six decision points under."""

from __future__ import annotations

from typing import Final, final

__all__ = ["OAuth2Events"]


@final
class OAuth2Events:
    """Where an application gets a word in, by name.

    Six moments. Each is dispatched under the name held here, and a listener
    registers under the very same name — a listener declaring one name while
    the code dispatches under another reaches nothing and fails silently, so
    the names live in one place and both sides read them from here.

    They are strings rather than event classes because that is what a
    deployment writes in a configuration file or a decorator, and because two
    of them are announced with an event class an add-on may replace.
    """

    USER_RESOLVE: Final[str] = "oauth2_server.user_resolve"
    """A grant that was handed a resource owner's own credentials wants a user.

    The only flow that ever sees a username and a password. A listener checks
    them however the application checks them and sets the user it resolved;
    leaving it unset refuses the request.
    """

    SCOPE_RESOLVE: Final[str] = "oauth2_server.scope_resolve"
    """The scopes a token is about to be granted are settled.

    Announced after the client's own registration has already narrowed them,
    and the set a listener leaves behind is the set written into the token —
    so this is the last word on what a token may do.
    """

    AUTHORIZATION_REQUEST_RESOLVE: Final[str] = "oauth2_server.authorization_request_resolve"
    """An authorization request is understood, and needs the owner's decision.

    A listener either resolves the request — approved or denied — or answers
    with a response of its own, which is how a consent page is shown.
    """

    TOKEN_REQUEST_RESOLVE: Final[str] = "oauth2_server.token_request_resolve"  # noqa: S105 -- an event name, not a secret
    """A token response is built and about to be sent.

    A listener may replace it, which is the seam for a deployment that has to
    add a field of its own to the answer.
    """

    PRE_SAVE_CLIENT: Final[str] = "oauth2_server.pre_save_client"
    """A client is about to be stored.

    A listener may change it, or put another client on the event to be stored
    instead. The default scopes a deployment configures are applied here.
    """

    ACCESS_TOKEN_EXTRA_CLAIMS_RESOLVE: Final[str] = (
        "oauth2_server.access_token_extra_claims_resolve"  # noqa: S105 -- an event name, not a secret
    )
    """An access token is about to be minted, before it is signed.

    A listener adds the claims it wants carried in the token. The names the
    token mints itself are refused, so a listener cannot quietly reissue the
    issuer, the expiry or the scope.
    """
