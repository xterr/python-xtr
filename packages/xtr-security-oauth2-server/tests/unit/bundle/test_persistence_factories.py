"""Every database manager is a singleton that asks for the named connection's session."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, Never

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from xtr_clock import MockClock
from xtr_orm import ConnectionRegistry
from xtr_orm.exception import UnknownConnectionError

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.orm import connections_of
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
    from typing import TypeAlias

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

pytestmark = pytest.mark.anyio

CONNECTION: Final = "reports"
"""A connection that is not the default one, so a manager handed the default is caught."""


def _clock() -> MockClock:
    """Return a frozen clock; none of these managers reads it here."""
    return MockClock(datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC))


def _clients() -> HeldClientManager:
    """Return a client store the revoker's factory can be handed."""
    return HeldClientManager(RecordingEventDispatcher())


def _built(registry: ConnectionRegistry) -> tuple[Manager, ...]:
    """Return one of every manager, each built over ``registry`` for ``CONNECTION``."""
    return (
        access_token_manager_factory(CONNECTION, True)(registry, _clock()),
        authorization_code_manager_factory(CONNECTION)(registry, _clock()),
        device_code_manager_factory(CONNECTION)(registry, _clock()),
        refresh_token_manager_factory(CONNECTION)(registry, _clock()),
        client_manager_factory(CONNECTION, Client)(registry, RecordingEventDispatcher()),
        credentials_revoker_factory(CONNECTION, True, True)(registry, _clients()),
    )


async def _session_asked_for(manager: Manager) -> AsyncSession:
    """Return the session ``manager`` asks the registry for.

    Private on purpose: how a manager reaches its session is nobody's business
    but its own, and asking it twice is what proves it holds none.
    """
    return await manager._session()


def test_every_factory_builds_the_manager_it_is_named_for() -> None:
    built = _built(connections_of(AsyncSession(), CONNECTION))

    assert isinstance(built[0], AccessTokenManager)
    assert isinstance(built[1], AuthorizationCodeManager)
    assert isinstance(built[2], DeviceCodeManager)
    assert isinstance(built[3], RefreshTokenManager)
    assert isinstance(built[4], ClientManager)
    assert isinstance(built[5], OrmCredentialsRevoker)


async def test_every_manager_asks_for_the_session_of_the_connection_that_was_named() -> None:
    # The whole reason these are factories: a manager that asked for the
    # default connection would be reading the right database only by accident.
    session = AsyncSession()
    registry = connections_of(session, CONNECTION)

    for manager in _built(registry):
        assert await _session_asked_for(manager) is session


async def test_a_manager_whose_connection_is_not_registered_is_refused() -> None:
    elsewhere = connections_of(AsyncSession(), "somewhere-else")

    for manager in _built(elsewhere):
        with pytest.raises(UnknownConnectionError):
            _ = await _session_asked_for(manager)


async def test_a_manager_asks_again_rather_than_keeping_the_session_it_was_given() -> None:
    # A singleton serves every request; one holding the first request's
    # session would write the second request's token into a closed unit of
    # work.
    handed = [AsyncSession(), AsyncSession()]
    registry = ConnectionRegistry("no-default")

    async def provide() -> AsyncSession:
        return handed.pop(0)

    registry.register(
        CONNECTION,
        engine=_never,
        migrator=_never,
        database=_never,
        session=provide,
    )
    manager = access_token_manager_factory(CONNECTION, True)(registry, _clock())

    first = await _session_asked_for(manager)
    second = await _session_asked_for(manager)

    assert first is not second


async def _never() -> Never:
    """Stand where a connection's other pieces would be; a manager asks for none."""
    raise AssertionError("a manager asks a registry only for a session")  # pragma: no cover
