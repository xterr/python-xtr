"""What an authorization request answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface

__all__ = ["AuthorizationRequestInterface"]


@runtime_checkable
class AuthorizationRequestInterface(Protocol):
    """An authorization request, from the moment it is read to the redirect.

    It is the one piece of state that crosses the consent step: the server
    reads a request, works out which client is asking and for what, and hands
    this over; something decides who the resource owner is and whether they
    approve; and the server is handed it back to finish the redirect.

    Everything here is therefore mutable — this is the object those two halves
    talk through — and a listener resolving consent sets the resource owner and
    the approval on it.

    It is a contract, not just a class, because a deployment may need to carry
    something extra across that step: an add-on that has to remember a
    parameter of the original request implements this and the server passes
    its request around unchanged.
    """

    def get_grant_type_id(self) -> str:
        """Return the grant the request is for."""
        ...

    def set_grant_type_id(self, grant_type_id: str) -> None:
        """Record that the request is for ``grant_type_id``."""
        ...

    def get_client(self) -> ClientEntityInterface:
        """Return the client asking."""
        ...

    def set_client(self, client: ClientEntityInterface) -> None:
        """Record that ``client`` is asking."""
        ...

    def get_user(self) -> UserEntityInterface | None:
        """Return the resource owner, or ``None`` before one is known."""
        ...

    def set_user(self, user: UserEntityInterface) -> None:
        """Record that ``user`` is the resource owner."""
        ...

    def get_scopes(self) -> Sequence[ScopeEntityInterface]:
        """Return the scopes asked for."""
        ...

    def set_scopes(self, scopes: Sequence[ScopeEntityInterface]) -> None:
        """Record that ``scopes`` were asked for."""
        ...

    def is_authorization_approved(self) -> bool:
        """Tell whether the resource owner approved the request."""
        ...

    def set_authorization_approved(self, authorization_approved: bool) -> None:
        """Record the resource owner's decision."""
        ...

    def get_redirect_uri(self) -> str | None:
        """Return the redirect URI the request named, or ``None`` for none."""
        ...

    def set_redirect_uri(self, redirect_uri: str | None) -> None:
        """Record the redirect URI the request named, ``None`` for none."""
        ...

    def get_state(self) -> str | None:
        """Return the state the request carried, or ``None`` for none."""
        ...

    def set_state(self, state: str) -> None:
        """Record the state the request carried, to send back unchanged."""
        ...

    def get_code_challenge(self) -> str | None:
        """Return the code challenge the request carried, or ``None``."""
        ...

    def set_code_challenge(self, code_challenge: str) -> None:
        """Record the code challenge the request carried."""
        ...

    def get_code_challenge_method(self) -> str | None:
        """Return how the code challenge was derived, or ``None``."""
        ...

    def set_code_challenge_method(self, code_challenge_method: str) -> None:
        """Record how the code challenge was derived."""
        ...
