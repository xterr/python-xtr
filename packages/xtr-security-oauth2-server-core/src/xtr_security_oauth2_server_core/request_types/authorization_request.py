"""The authorization request the server reads, hands over, and gets back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from .authorization_request_interface import AuthorizationRequestInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

__all__ = ["AuthorizationRequest"]


class AuthorizationRequest(AuthorizationRequestInterface):
    """What the server worked out about an authorization request, so far.

    Built empty and filled in as the request is handled: the server sets the
    grant, the client, the scopes and the redirect URI it validated, then
    whatever resolves consent sets the resource owner and the approval, and
    the server reads the lot to build the redirect.

    The grant and the client have no sensible empty value — a request with no
    client is not a request — so reading either before it is set says so
    rather than handing back something made up. Everything else genuinely can
    be absent: a request need not name a redirect URI, carry state, or use a
    code challenge.

    This is also the class an add-on extends. The request is the one piece of
    state that crosses the consent step, so an extension having to remember a
    parameter of the original authorization request — an identity nonce, the
    instant the resource owner authenticated — subclasses this, adds what it
    carries, and hands its own back from ``create_authorization_request()``;
    the grant goes on filling in everything here as it always did.
    """

    def __init__(self) -> None:
        """Start an empty request, nothing decided about it yet."""
        self._grant_type_id: str | None = None
        self._client: ClientEntityInterface | None = None
        self._user: UserEntityInterface | None = None
        self._scopes: tuple[ScopeEntityInterface, ...] = ()
        self._authorization_approved: bool = False
        self._redirect_uri: str | None = None
        self._state: str | None = None
        self._code_challenge: str | None = None
        self._code_challenge_method: str | None = None

    @override
    def get_grant_type_id(self) -> str:
        """Return the grant the request is for.

        Raises:
            InvalidArgumentError: When nothing has set it, which means the
                request is being read before it was understood.
        """
        if self._grant_type_id is None:
            raise InvalidArgumentError(
                "This authorization request names no grant type yet; it is set as the "
                "request is validated, before the request is handed on.",
            )
        return self._grant_type_id

    @override
    def set_grant_type_id(self, grant_type_id: str) -> None:
        """Record that the request is for ``grant_type_id``."""
        self._grant_type_id = grant_type_id

    @override
    def get_client(self) -> ClientEntityInterface:
        """Return the client asking.

        Raises:
            InvalidArgumentError: When nothing has set it, which means the
                request is being read before it was understood.
        """
        if self._client is None:
            raise InvalidArgumentError(
                "This authorization request names no client yet; it is set as the request "
                "is validated, before the request is handed on.",
            )
        return self._client

    @override
    def set_client(self, client: ClientEntityInterface) -> None:
        """Record that ``client`` is asking."""
        self._client = client

    @override
    def get_user(self) -> UserEntityInterface | None:
        """Return the resource owner, or ``None`` before one is known."""
        return self._user

    @override
    def set_user(self, user: UserEntityInterface) -> None:
        """Record that ``user`` is the resource owner."""
        self._user = user

    @override
    def get_scopes(self) -> Sequence[ScopeEntityInterface]:
        """Return the scopes asked for, in the order they were set."""
        return self._scopes

    @override
    def set_scopes(self, scopes: Sequence[ScopeEntityInterface]) -> None:
        """Record that ``scopes`` were asked for.

        Copied, so a caller that goes on to change its own list does not
        change what this request says was asked for.
        """
        self._scopes = tuple(scopes)

    @override
    def is_authorization_approved(self) -> bool:
        """Tell whether the resource owner approved the request."""
        return self._authorization_approved

    @override
    def set_authorization_approved(self, authorization_approved: bool) -> None:
        """Record the resource owner's decision."""
        self._authorization_approved = authorization_approved

    @override
    def get_redirect_uri(self) -> str | None:
        """Return the redirect URI the request named, or ``None`` for none."""
        return self._redirect_uri

    @override
    def set_redirect_uri(self, redirect_uri: str | None) -> None:
        """Record the redirect URI the request named, ``None`` for none."""
        self._redirect_uri = redirect_uri

    @override
    def get_state(self) -> str | None:
        """Return the state the request carried, or ``None`` for none."""
        return self._state

    @override
    def set_state(self, state: str) -> None:
        """Record the state the request carried, to send back unchanged."""
        self._state = state

    @override
    def get_code_challenge(self) -> str | None:
        """Return the code challenge the request carried, or ``None``."""
        return self._code_challenge

    @override
    def set_code_challenge(self, code_challenge: str) -> None:
        """Record the code challenge the request carried."""
        self._code_challenge = code_challenge

    @override
    def get_code_challenge_method(self) -> str | None:
        """Return how the code challenge was derived, or ``None``."""
        return self._code_challenge_method

    @override
    def set_code_challenge_method(self, code_challenge_method: str) -> None:
        """Record how the code challenge was derived."""
        self._code_challenge_method = code_challenge_method

    @override
    def __repr__(self) -> str:
        """Name the grant and the decision, and nothing else.

        The state is what binds the redirect back to the browser that started
        the flow, and the code challenge is what binds it to the client: a log
        line carrying either hands a reader a piece of somebody's flow. The
        client and the scopes are left out for brevity, not secrecy — the
        request is readable in full where it is being handled.
        """
        return (
            f"{type(self).__name__}(grant_type_id={self._grant_type_id!r}, "
            f"authorization_approved={self._authorization_approved!r})"
        )
