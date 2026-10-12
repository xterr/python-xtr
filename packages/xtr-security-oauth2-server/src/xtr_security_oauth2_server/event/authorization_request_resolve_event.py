"""An authorization request is understood, and needs the resource owner's answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ResponseInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface
    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server.value_object.scope import Scope

__all__ = ["AuthorizationRequestResolveEvent"]


class AuthorizationRequestResolveEvent(Event):
    """Carries everything a consent decision needs, and takes the answer back.

    This is the one place an application has to answer: nobody but the
    deployment knows whether this resource owner, in front of this client,
    asking for these scopes, said yes. A listener does one of two things —
    resolve the request, or answer with a response of its own, which is how a
    consent page is shown and how the form posting back reaches the flow
    again.

    Either one stops the listeners after it. A decision is a decision, and two
    listeners quietly overruling each other is how a consent screen gets
    skipped.

    A request is denied until something approves it. The expensive mistake
    here is defaulting to approval, so the default is the refusal.
    """

    APPROVED: ClassVar[bool] = True
    """The resource owner said yes."""

    DENIED: ClassVar[bool] = False
    """The resource owner said no, or nobody asked them."""

    def __init__(
        self,
        authorization_request: AuthorizationRequestInterface,
        scopes: Sequence[Scope],
        client: ClientInterface,
        user: UserInterface,
    ) -> None:
        """Announce ``authorization_request``, as shown to ``user``."""
        self._authorization_request: AuthorizationRequestInterface = authorization_request
        self._scopes: tuple[Scope, ...] = tuple(scopes)
        self._client: ClientInterface = client
        self._user: UserInterface = user
        self._authorization_resolution: bool = self.DENIED
        self._response: ResponseInterface | None = None

    def get_authorization_resolution(self) -> bool:
        """Return the decision, which is a refusal until something resolves it."""
        return self._authorization_resolution

    def resolve_authorization(self, authorization_resolution: bool) -> Self:
        """Decide the request, and stop the listeners after this one.

        Drops any response set earlier: a listener that had decided to show a
        consent page and then resolved the request meant the decision, and
        sending both would be sending a page instead of the redirect the
        client is waiting for.
        """
        self._authorization_resolution = authorization_resolution
        self._response = None
        self.stop_propagation()

        return self

    def get_response(self) -> ResponseInterface | None:
        """Return the response a listener set, or ``None`` when none did."""
        return self._response

    def set_response(self, response: ResponseInterface) -> Self:
        """Answer with ``response``, and stop the listeners after this one."""
        self._response = response
        self.stop_propagation()

        return self

    def get_grant_type_id(self) -> str:
        """Return the grant the request is for."""
        return self._authorization_request.get_grant_type_id()

    def get_client(self) -> ClientInterface:
        """Return the client asking, as it is stored."""
        return self._client

    def get_user(self) -> UserInterface:
        """Return the resource owner the request is being shown to."""
        return self._user

    def set_user(self, user: UserInterface) -> Self:
        """Record that ``user`` is the resource owner answering."""
        self._user = user

        return self

    def get_scopes(self) -> Sequence[Scope]:
        """Return the scopes asked for, as they are stored."""
        return self._scopes

    def is_authorization_approved(self) -> bool:
        """Tell whether the request itself already carries an approval.

        The request's own flag, not this event's decision: it is what a
        consent form posting back sets, so a listener can tell a second pass
        from the first.
        """
        return self._authorization_request.is_authorization_approved()

    def get_redirect_uri(self) -> str | None:
        """Return the redirect URI the request named, or ``None`` for none."""
        return self._authorization_request.get_redirect_uri()

    def get_state(self) -> str | None:
        """Return the state the request carried, or ``None`` for none."""
        return self._authorization_request.get_state()

    def get_code_challenge(self) -> str | None:
        """Return the code challenge the request carried, or ``None``."""
        return self._authorization_request.get_code_challenge()

    def get_code_challenge_method(self) -> str | None:
        """Return how the code challenge was derived, or ``None``."""
        return self._authorization_request.get_code_challenge_method()

    @override
    def __repr__(self) -> str:
        """Name the client, the decision, and whether a response was set.

        The state binds the redirect back to the browser that started the
        flow and the code challenge binds it to the client, so neither is
        shown; the resource owner is left out as well, since a log line
        naming who was asked to consent to what is a record nobody asked for.
        """
        return (
            f"{type(self).__name__}(client={self._client!r}, "
            f"resolution={self._authorization_resolution!r}, "
            f"response={self._response is not None!r})"
        )
