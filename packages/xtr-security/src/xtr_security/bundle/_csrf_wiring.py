"""The forgery-token machinery the bundle owns for the csrf package.

The csrf package ships no bundle of its own: its manager is wired here, over
the session the request reattached. The session is parked on the request's
security state by the context listener while the request runs — after the
container has built the services that want it — so the storage the manager
reads through holds the request's park, not the session, and reads it anew on
every call. Whatever moment a consumer is built in, the tokens it mints and
checks travel in the session of the request it answers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_csrf.csrf_token_manager import CsrfTokenManager
from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface
from xtr_security_csrf.token_storage.clearable_token_storage_interface import (
    ClearableTokenStorageInterface,
)
from xtr_security_csrf.token_storage.session_token_storage import SessionTokenStorage
from xtr_security_http._parked_session import (
    parked_session_of,
)
from xtr_security_http.exception import MissingSessionError

from xtr_security.bundle.authenticator_configs import FormLoginConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security.firewall_config import FirewallConfig

__all__ = [
    "ParkedRequest",
    "ParkedSessionTokenStorage",
    "firewall_asks_for_csrf",
    "form_login_asks_for_csrf",
    "register_csrf_token_manager",
]


@final
class ParkedRequest:
    """The request the firewall is running, for the services the chain builds.

    The chain's steps receive the request as an argument; the services they
    hold at construction do not. This is the bridge: a listener ahead of the
    firewall parks the request here, and a service built anywhere in the
    request — before the chain runs, or after it — reads the same request
    through the park, on every call, never holding more than the park itself.
    """

    __slots__ = ("request",)

    request: ServerRequestInterface | None
    """The request being served, parked before the firewall runs."""

    def __init__(self) -> None:
        """Start with no request: one is parked ahead of the firewall."""
        self.request = None


@final
class ParkedSessionTokenStorage(ClearableTokenStorageInterface):
    """Keeps token values in the session the request it answers reattached.

    The session is not held: the request's park is read on every call,
    because the moment this storage is built says nothing about the moment
    the session is parked. A chain step is built before the chain runs —
    before the context listener has reattached anything — and a resolver is
    built after the request has passed the whole chain; both hold this one
    storage, and both read the session their own request parked.

    A request whose state carries no session is refused loudly: it reached
    forgery-token machinery that only a session can back, and answering as
    though no token existed would read as protection while storing nothing.
    """

    __slots__ = ("_request_park",)

    def __init__(self, request_park: ParkedRequest) -> None:
        """Record the park the request was handed to the chain in."""
        self._request_park = request_park

    async def _storage(self) -> SessionTokenStorage:
        """Return the storage over the session this request's state carries."""
        request = self._request_park.request
        if request is None:
            raise MissingSessionError
        session = parked_session_of(request)
        if session is None:
            raise MissingSessionError
        return SessionTokenStorage(session)

    @override
    async def get_token(self, token_id: str) -> str:
        """Return the value stored under ``token_id``.

        Raises:
            TokenNotFoundError: When no value is stored under the id.
            MissingSessionError: When the request's state carries no session.
        """
        return await (await self._storage()).get_token(token_id)

    @override
    async def set_token(self, token_id: str, token: str) -> None:
        """Store ``token`` under ``token_id``, and remember the id."""
        await (await self._storage()).set_token(token_id, token)

    @override
    async def has_token(self, token_id: str) -> bool:
        """Tell whether a value is stored under ``token_id``."""
        return await (await self._storage()).has_token(token_id)

    @override
    async def remove_token(self, token_id: str) -> str | None:
        """Drop the value under ``token_id``, returning what it held."""
        return await (await self._storage()).remove_token(token_id)

    @override
    async def clear(self) -> None:
        """Drop every token this storage minted, and nothing else."""
        await (await self._storage()).clear()


def register_csrf_token_manager(services: ServiceConfigurator) -> None:
    """Register the request's token storage and the manager over it.

    The manager answers as the application's one
    :class:`~xtr_security_csrf.csrf_token_manager_interface.CsrfTokenManagerInterface`
    service, which is the name the route marker's checker watches: with the
    manager registered the checker stays, and the bundle never builds a
    checker that cannot answer. Both services are scoped — they belong to
    one request, holding its message — and built only when a firewall's
    configuration asks for a forgery token, so an application that asks
    nowhere carries none of this.
    """

    def request_park() -> ParkedRequest:
        """Build the park the request's own services read the request through."""
        return ParkedRequest()

    request_park.__annotations__ = {"return": ParkedRequest}
    _ = services.set(request_park, lifetime="scoped")

    def parked_session_token_storage(request_park: ParkedRequest) -> ParkedSessionTokenStorage:
        """Build the storage over the park of the request being served."""
        return ParkedSessionTokenStorage(request_park)

    parked_session_token_storage.__annotations__ = {
        "request_park": ParkedRequest,
        "return": ParkedSessionTokenStorage,
    }
    _ = services.set(parked_session_token_storage, lifetime="scoped")
    services.alias(ClearableTokenStorageInterface, ParkedSessionTokenStorage)

    def csrf_token_manager(storage: ClearableTokenStorageInterface) -> CsrfTokenManager:
        """Build the manager that mints and vouches for the request's tokens."""
        return CsrfTokenManager(storage)

    csrf_token_manager.__annotations__ = {
        "storage": ClearableTokenStorageInterface,
        "return": CsrfTokenManager,
    }
    _ = services.set(csrf_token_manager, lifetime="scoped")
    services.alias(CsrfTokenManagerInterface, CsrfTokenManager)
    # The listener that hands the chain's services the request they are
    # built for: without it the storage would hold the park of no request.
    services.load("xtr_security.bundle._csrf_listeners")


def firewall_asks_for_csrf(firewall: FirewallConfig) -> bool:
    """Tell whether the firewall's configuration asks for a forgery token.

    A form login whose form carries one, a logout that must be proven, and a
    logout that drops its tokens — each needs the manager, so each wires it.
    Nothing else does: the machinery is opt-in, the way the protection is.
    """
    if firewall.logout is not None and (
        firewall.logout.enable_csrf or firewall.logout.clear_csrf_tokens
    ):
        return True
    return form_login_asks_for_csrf(firewall)


def form_login_asks_for_csrf(firewall: FirewallConfig) -> bool:
    """Tell whether one of the firewall's form logins carries a forgery token.

    The badge such a form's passport carries is what the passport check's
    listener settles, so the listener joins exactly these firewalls — a
    firewall that asks nowhere else mints no badge for it to check.
    """
    return any(
        isinstance(authenticator, FormLoginConfig) and authenticator.enable_csrf
        for authenticator in firewall.authenticators
    )
