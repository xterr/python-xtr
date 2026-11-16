"""Every database manager is a singleton that opens a unit of its own on the named connection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, TypeVar, final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override
from xtr_clock import MockClock
from xtr_dependency_injection.exception import ServiceNotFoundError
from xtr_service_contracts import ContainerInterface

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import client_model
from tests.support.orm import stored
from tests.support.users import SecurityUser
from xtr_security_oauth2_server.bundle._persistence_factories import (
    access_token_manager_factory,
    authorization_code_manager_factory,
    client_manager_factory,
    credentials_revoker_factory,
    device_code_manager_factory,
    refresh_token_manager_factory,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import (
    ClientManager as HeldClientManager,
)
from xtr_security_oauth2_server.manager.orm.access_token_manager import AccessTokenManager
from xtr_security_oauth2_server.manager.orm.authorization_code_manager import (
    AuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.orm.client_manager import ClientManager
from xtr_security_oauth2_server.manager.orm.device_code_manager import DeviceCodeManager
from xtr_security_oauth2_server.manager.orm.refresh_token_manager import RefreshTokenManager
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.service.credentials_revoker.orm_credentials_revoker import (
    OrmCredentialsRevoker,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable
    from pathlib import Path
    from typing import TypeAlias

    from xtr_dependency_injection import ScopeFactoryInterface

    #: Every manager a stored deployment is wired with. They have no interface
    #: in common beyond the one each fills, and what is asserted here is
    #: something all of them do.
    Manager: TypeAlias = (
        AccessTokenManager
        | AuthorizationCodeManager
        | DeviceCodeManager
        | RefreshTokenManager
        | ClientManager
        | OrmCredentialsRevoker
    )

    #: What a unit of work was asked for: a service, and the qualifier naming it.
    Asked: TypeAlias = tuple[type[object], Hashable | None]

pytestmark = pytest.mark.anyio

_T = TypeVar("_T")

CONNECTION: Final = "reports"
"""A connection that is not the default one, so a manager asking for the default is caught."""


@final
class _AskedError(Exception):
    """Raised by a recorded unit of work once it is asked for a service, so the caller stops."""


@final
class _RecordingUnit(ContainerInterface):
    """A unit of work noting every service it is asked for, and holding none."""

    __slots__ = ("_asked",)

    def __init__(self, asked: list[Asked]) -> None:
        self._asked = asked

    @override
    async def get(self, service: type[_T], /, qualifier: Hashable | None = None) -> _T:
        """Note what was asked for, then refuse it."""
        self._asked.append((service, qualifier))
        raise _AskedError

    @override
    def has(self, service: type[object], /, qualifier: Hashable | None = None) -> bool:
        return False

    @override
    def get_parameter(self, name: str, /) -> object:
        raise LookupError(name)

    @override
    def has_parameter(self, name: str, /) -> bool:
        return False


@final
class _RecordingScopeFactory:
    """A scope factory noting every unit opened on it, and what each was asked for.

    Its units hand nothing out, so a manager stops at the first service it asks
    for: what it does with a session is for the managers' own tests, which run
    against a real database. What is asserted here is how it reaches one.
    """

    __slots__ = ("asked", "joins")

    def __init__(self) -> None:
        self.joins: list[bool] = []
        self.asked: list[Asked] = []

    @asynccontextmanager
    async def unit_of_work(self, *, join: bool = True) -> AsyncGenerator[ContainerInterface, None]:
        """Note the ``join`` a unit is opened with, and hand out one noting what it is asked."""
        self.joins.append(join)
        yield _RecordingUnit(self.asked)


def _clock() -> MockClock:
    """Return a frozen clock; none of these managers reads it here."""
    return MockClock(datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC))


def _clients() -> HeldClientManager:
    """Return a client store the revoker's factory can be handed."""
    return HeldClientManager(RecordingEventDispatcher())


def _built(scope_factory: ScopeFactoryInterface) -> tuple[Manager, ...]:
    """Return one of every manager, each built over ``scope_factory`` for ``CONNECTION``."""
    return (
        access_token_manager_factory(CONNECTION, True)(scope_factory, _clock()),
        authorization_code_manager_factory(CONNECTION)(scope_factory, _clock()),
        device_code_manager_factory(CONNECTION)(scope_factory, _clock()),
        refresh_token_manager_factory(CONNECTION)(scope_factory, _clock()),
        client_manager_factory(CONNECTION, Client)(scope_factory, RecordingEventDispatcher()),
        credentials_revoker_factory(CONNECTION, True, True)(scope_factory, _clients()),
    )


async def _reach_the_store(manager: Manager) -> None:
    """Ask ``manager`` for something it has to reach the store for.

    The client manager is asked to remove a client rather than to read one: a
    read names the client's mapped table before it opens a unit, and nothing
    maps one here.
    """
    if isinstance(manager, OrmCredentialsRevoker):
        await manager.revoke_credentials_for_user(SecurityUser())
    elif isinstance(manager, ClientManager):
        await manager.remove(client_model())
    else:
        _ = await manager.find("an-identifier")


def test_every_factory_builds_the_manager_it_is_named_for() -> None:
    built = _built(_RecordingScopeFactory())

    assert isinstance(built[0], AccessTokenManager)
    assert isinstance(built[1], AuthorizationCodeManager)
    assert isinstance(built[2], DeviceCodeManager)
    assert isinstance(built[3], RefreshTokenManager)
    assert isinstance(built[4], ClientManager)
    assert isinstance(built[5], OrmCredentialsRevoker)


async def test_every_manager_asks_for_the_session_of_the_connection_that_was_named() -> None:
    # The whole reason these are factories: a manager that asked for the
    # default connection would be reading the right database only by accident.
    scope_factory = _RecordingScopeFactory()
    built = _built(scope_factory)

    for manager in built:
        with pytest.raises(_AskedError):
            await _reach_the_store(manager)

    assert scope_factory.asked == [(AsyncSession, CONNECTION)] * len(built)


async def test_a_manager_whose_connection_is_not_registered_is_refused(tmp_path: Path) -> None:
    # An application holding the default connection only: a manager built for
    # another one is refused, rather than quietly reading the default.
    async with stored(tmp_path) as database:
        built = _built(await database.scope_factory())

        for manager in built:
            with pytest.raises(ServiceNotFoundError):
                await _reach_the_store(manager)


async def test_every_call_opens_a_unit_of_its_own_rather_than_joining_the_one_under_way() -> None:
    # A singleton serves every request. Working in the request's unit would
    # commit whatever the application has pending there, and keeping the unit
    # one call opened would write the next call's token into a closed one.
    scope_factory = _RecordingScopeFactory()
    built = _built(scope_factory)

    for manager in (*built, *built):
        with pytest.raises(_AskedError):
            await _reach_the_store(manager)

    assert scope_factory.joins == [False] * (2 * len(built))
