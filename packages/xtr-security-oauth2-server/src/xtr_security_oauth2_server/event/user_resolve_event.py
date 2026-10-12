"""A resource owner's own credentials were sent, and someone has to check them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface
    from xtr_security_oauth2_server.value_object.grant import Grant

__all__ = ["UserResolveEvent"]


class UserResolveEvent(Event):
    """Carries a username and a password, and waits for the user they belong to.

    The one event in this package that ever sees a resource owner's own
    credentials, because it serves the one flow where a client sends them.
    Checking them is the application's: a listener resolves the user, and
    leaving it unresolved refuses the request without saying which half was
    wrong.

    The client is here as well, so a listener may let one client check
    credentials and refuse another.
    """

    def __init__(
        self,
        username: str,
        password: str,
        grant: Grant,
        client: ClientInterface,
    ) -> None:
        """Announce the credentials ``client`` sent under ``grant``."""
        self._username: str = username
        self._password: str = password
        self._grant: Grant = grant
        self._client: ClientInterface = client
        self._user: UserInterface | None = None

    def get_username(self) -> str:
        """Return the name the request carried."""
        return self._username

    def get_password(self) -> str:
        """Return the password the request carried."""
        return self._password

    def get_grant(self) -> Grant:
        """Return the grant asking."""
        return self._grant

    def get_client(self) -> ClientInterface:
        """Return the client asking."""
        return self._client

    def get_user(self) -> UserInterface | None:
        """Return the user a listener resolved, or ``None`` when none did."""
        return self._user

    def set_user(self, user: UserInterface | None) -> Self:
        """Resolve the credentials to ``user``, or to nobody with ``None``."""
        self._user = user

        return self

    @override
    def __repr__(self) -> str:
        """Name the grant and whether a user was resolved, and nothing else.

        The username and the password are both the request's own, and either
        in a log line is a credential written down. Whether a user came out is
        what a reader actually needs.
        """
        resolved = self._user is not None

        return f"{type(self).__name__}(grant={self._grant!r}, resolved={resolved!r})"
