"""What the authorization server announces while it answers a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["RequestEvent"]


class RequestEvent(Event):
    """Something worth hearing about happened while a request was being answered.

    The server and its grants announce these as they work, so an application
    can audit, rate-limit or alert without the protocol code knowing it is
    watched. Every one of them carries the request it happened during; the two
    that also carry what was issued have their own classes.

    A listener may stop the event, and the listeners after it are then skipped.

    The names are the keys listeners register under, so they carry the package
    in front: an application's dispatcher is one namespace shared by every
    library in it, and ``access_token.issued`` on its own would be anyone's.

    ```python
    @as_event_listener(RequestEvent.ACCESS_TOKEN_ISSUED)
    async def record(event: RequestAccessTokenEvent) -> None: ...
    ```
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_name", "_request")

    #: A client could not be authenticated at the token endpoint.
    CLIENT_AUTHENTICATION_FAILED: Final[str] = "oauth2_server.client.authentication.failed"

    #: A user's own credentials were refused, in the grant that asks for them.
    USER_AUTHENTICATION_FAILED: Final[str] = "oauth2_server.user.authentication.failed"

    #: A refresh token was presented by a client it was not issued to.
    REFRESH_TOKEN_CLIENT_FAILED: Final[str] = "oauth2_server.refresh_token.client.failed"  # noqa: S105 -- an event name, not a secret

    #: A refresh token was issued.
    REFRESH_TOKEN_ISSUED: Final[str] = "oauth2_server.refresh_token.issued"  # noqa: S105 -- an event name, not a secret

    #: An access token was issued.
    ACCESS_TOKEN_ISSUED: Final[str] = "oauth2_server.access_token.issued"  # noqa: S105 -- an event name, not a secret

    def __init__(self, name: str, request: ServerRequestInterface) -> None:
        """Announce ``name``, happening while ``request`` was being answered."""
        self._name: str = name
        self._request: ServerRequestInterface = request

    def get_name(self) -> str:
        """Return the name this event was announced under.

        The dispatcher is handed the same name, so a listener registered for
        several of them can tell which one it is hearing.
        """
        return self._name

    def get_request(self) -> ServerRequestInterface:
        """Return the request this happened during."""
        return self._request

    @override
    def __repr__(self) -> str:
        """Name the event and what it was announced under, and nothing else.

        What the event carries is a request full of credentials, and in the
        token events a token besides; an event that lands in a log line should
        not take either with it.
        """
        return f"{type(self).__name__}(name={self._name!r})"
