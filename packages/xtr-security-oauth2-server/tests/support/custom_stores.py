"""The stores an application that keeps its own clients and credentials answers with.

What ``persistence.custom`` is for: an application names six services of its
own and the bundle registers no store at all. These stand in for them. Each one
delegates to the shipped in-process manager, so what the flows meet is real
behaviour and what is being proved is the wiring — that each interface reaches
the class the application named.

They are left open to subclassing on purpose: one fixture application
registers a subclass of each as a service, and another names *these* so that
nothing registers them, which is how the refusal is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_event_dispatcher_contracts import EventDispatcherInterface

from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import (
    AccessTokenManager as HeldAccessTokenManager,
)
from xtr_security_oauth2_server.manager.in_memory.authorization_code_manager import (
    AuthorizationCodeManager as HeldAuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import (
    ClientManager as HeldClientManager,
)
from xtr_security_oauth2_server.manager.in_memory.device_code_manager import (
    DeviceCodeManager as HeldDeviceCodeManager,
)
from xtr_security_oauth2_server.manager.in_memory.refresh_token_manager import (
    RefreshTokenManager as HeldRefreshTokenManager,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.manager.client_filter import ClientFilter
    from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface
    from xtr_security_oauth2_server.model.authorization_code_interface import (
        AuthorizationCodeInterface,
    )
    from xtr_security_oauth2_server.model.client_interface import ClientInterface
    from xtr_security_oauth2_server.model.device_code_interface import DeviceCodeInterface
    from xtr_security_oauth2_server.model.refresh_token_interface import RefreshTokenInterface

__all__ = [
    "ApplicationAccessTokenStore",
    "ApplicationAuthorizationCodeStore",
    "ApplicationClientStore",
    "ApplicationCredentialsRevoker",
    "ApplicationDeviceCodeStore",
    "ApplicationRefreshTokenStore",
]


class ApplicationClientStore(ClientManagerInterface):
    """The application's own client registry."""

    _held: HeldClientManager

    def __init__(self, dispatcher: EventDispatcherInterface) -> None:
        self._held = HeldClientManager(dispatcher)

    @override
    async def find(self, identifier: str) -> ClientInterface | None:
        return await self._held.find(identifier)

    @override
    async def save(self, client: ClientInterface) -> None:
        await self._held.save(client)

    @override
    async def remove(self, client: ClientInterface) -> None:
        await self._held.remove(client)

    @override
    async def list(self, client_filter: ClientFilter | None) -> Sequence[ClientInterface]:
        return await self._held.list(client_filter)


class ApplicationAccessTokenStore(AccessTokenManagerInterface):
    """The application's own access-token store."""

    _held: HeldAccessTokenManager

    def __init__(self, clock: ClockInterface) -> None:
        self._held = HeldAccessTokenManager(clock)

    @override
    async def find(self, identifier: str) -> AccessTokenInterface | None:
        return await self._held.find(identifier)

    @override
    async def save(self, access_token: AccessTokenInterface) -> None:
        await self._held.save(access_token)

    @override
    async def clear_expired(self) -> int:
        return await self._held.clear_expired()


class ApplicationAuthorizationCodeStore(AuthorizationCodeManagerInterface):
    """The application's own authorization-code store."""

    _held: HeldAuthorizationCodeManager

    def __init__(self, clock: ClockInterface) -> None:
        self._held = HeldAuthorizationCodeManager(clock)

    @override
    async def find(self, identifier: str) -> AuthorizationCodeInterface | None:
        return await self._held.find(identifier)

    @override
    async def save(self, auth_code: AuthorizationCodeInterface) -> None:
        await self._held.save(auth_code)

    @override
    async def clear_expired(self) -> int:
        return await self._held.clear_expired()


class ApplicationRefreshTokenStore(RefreshTokenManagerInterface):
    """The application's own refresh-token store."""

    _held: HeldRefreshTokenManager

    def __init__(self, clock: ClockInterface) -> None:
        self._held = HeldRefreshTokenManager(clock)

    @override
    async def find(self, identifier: str) -> RefreshTokenInterface | None:
        return await self._held.find(identifier)

    @override
    async def save(self, refresh_token: RefreshTokenInterface) -> None:
        await self._held.save(refresh_token)

    @override
    async def revoke(self, identifier: str) -> bool:
        return await self._held.revoke(identifier)

    @override
    async def clear_expired(self) -> int:
        return await self._held.clear_expired()


class ApplicationDeviceCodeStore(DeviceCodeManagerInterface):
    """The application's own device-code store."""

    _held: HeldDeviceCodeManager

    def __init__(self, clock: ClockInterface) -> None:
        self._held = HeldDeviceCodeManager(clock)

    @override
    async def find(self, identifier: str) -> DeviceCodeInterface | None:
        return await self._held.find(identifier)

    @override
    async def find_by_user_code(self, code: str) -> DeviceCodeInterface | None:
        return await self._held.find_by_user_code(code)

    @override
    async def save(self, device_code: DeviceCodeInterface) -> None:
        await self._held.save(device_code)

    @override
    async def clear_expired(self) -> int:
        return await self._held.clear_expired()


class ApplicationCredentialsRevoker(CredentialsRevokerInterface):
    """What the application withdraws a holder's credentials through.

    It records who was withdrawn rather than doing it: the stores it would
    reach are the application's, and what a test needs to see is that the
    bundle asked *this* one.
    """

    withdrawn: list[str]

    def __init__(self) -> None:
        self.withdrawn = []

    @override
    async def revoke_credentials_for_user(self, user: UserInterface) -> None:
        self.withdrawn.append(user.get_user_identifier())

    @override
    async def revoke_credentials_for_client(self, client: ClientInterface) -> None:
        self.withdrawn.append(client.get_identifier())
