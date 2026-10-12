"""Taking back everything a user or a client holds, one statement per table."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_clock import MockClock
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import (
    LATER,
    NOW,
    access_token_model,
    authorization_code_model,
    client_model,
    device_code_model,
    refresh_token_model,
)
from tests.support.orm import CONNECTION, connections_of, orm_driver, stored
from tests.support.users import SecurityUser
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
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.orm import Database

pytestmark = pytest.mark.anyio

_OTHER = "client-2"
"""A second client, so a revocation is shown to leave the rest alone."""


def test_it_declares_the_credentials_revoker_contract() -> None:
    assert CredentialsRevokerInterface in OrmCredentialsRevoker.__mro__


@final
class _Store:
    """One session's worth of managers, and the revoker over the same session."""

    __slots__ = (
        "access_tokens",
        "authorization_codes",
        "clients",
        "device_codes",
        "refresh_tokens",
        "revoker",
    )

    def __init__(
        self,
        database: Database,
        *,
        persist_access_token: bool = True,
        enable_device_code_grant: bool = True,
    ) -> None:
        session = database.session()
        # Every manager and the revoker share one session, as they do inside
        # one request: each asks the registry, and this registry answers with
        # the session this store was built on.
        connections = connections_of(session)
        clock = MockClock(NOW)
        self.clients = ClientManager(
            connections,
            CONNECTION,
            RecordingEventDispatcher(),
            Client,
        )
        self.access_tokens = AccessTokenManager(
            connections,
            CONNECTION,
            clock,
            persist_access_token,
        )
        self.authorization_codes = AuthorizationCodeManager(connections, CONNECTION, clock)
        self.refresh_tokens = RefreshTokenManager(connections, CONNECTION, clock)
        self.device_codes = DeviceCodeManager(connections, CONNECTION, clock)
        self.revoker = OrmCredentialsRevoker(
            connections,
            CONNECTION,
            self.clients,
            persist_access_token,
            enable_device_code_grant,
        )


async def _issued(store: _Store, user: str | None = "user-1", client: str = "client-1") -> None:
    """Issue one of each credential to ``client`` on behalf of ``user``."""
    stored_client = await store.clients.find(client)
    assert stored_client is not None
    token = access_token_model(f"at-{client}-{user}", LATER, stored_client, user)
    await store.access_tokens.save(token)
    await store.refresh_tokens.save(refresh_token_model(f"rt-{client}-{user}", LATER, token))
    await store.authorization_codes.save(
        authorization_code_model(f"ac-{client}-{user}", LATER, stored_client, user),
    )
    await store.device_codes.save(
        device_code_model(
            f"dc-{client}-{user}",
            LATER,
            f"UC{client}{user}"[:8],
            stored_client,
            user_identifier=user,
        ),
    )


async def _revoked(
    store: _Store,
    user: str | None = "user-1",
    client: str = "client-1",
) -> dict[str, bool | None]:
    """Return whether each credential issued to ``client`` for ``user`` is revoked."""
    access_token = await store.access_tokens.find(f"at-{client}-{user}")
    refresh_token = await store.refresh_tokens.find(f"rt-{client}-{user}")
    authorization_code = await store.authorization_codes.find(f"ac-{client}-{user}")
    device_code = await store.device_codes.find(f"dc-{client}-{user}")

    return {
        "access_token": access_token.is_revoked() if access_token is not None else None,
        "refresh_token": refresh_token is not None and refresh_token.is_revoked(),
        "authorization_code": authorization_code is not None and authorization_code.is_revoked(),
        "device_code": device_code is not None and device_code.is_revoked(),
    }


async def test_it_revokes_every_credential_a_user_holds(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        store = _Store(database)
        await store.clients.save(client_model())
        await _issued(store)

        await store.revoker.revoke_credentials_for_user(SecurityUser("user-1"))

        assert await _revoked(store) == {
            "access_token": True,
            "refresh_token": True,
            "authorization_code": True,
            "device_code": True,
        }


async def test_it_leaves_the_credentials_of_another_user_alone(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        store = _Store(database)
        await store.clients.save(client_model())
        await _issued(store, "user-1")
        await _issued(store, "user-2")

        await store.revoker.revoke_credentials_for_user(SecurityUser("user-1"))

        assert await _revoked(store, "user-2") == {
            "access_token": False,
            "refresh_token": False,
            "authorization_code": False,
            "device_code": False,
        }


async def test_it_revokes_every_credential_a_client_holds(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        store = _Store(database)
        await store.clients.save(client_model())
        await _issued(store)

        await store.revoker.revoke_credentials_for_client(client_model())

        assert await _revoked(store) == {
            "access_token": True,
            "refresh_token": True,
            "authorization_code": True,
            "device_code": True,
        }


async def test_it_leaves_the_credentials_of_another_client_alone(tmp_path: Path) -> None:
    async with stored(tmp_path) as database:
        store = _Store(database)
        await store.clients.save(client_model())
        await store.clients.save(client_model(_OTHER))
        await _issued(store, client="client-1")
        await _issued(store, client=_OTHER)

        await store.revoker.revoke_credentials_for_client(client_model())

        assert await _revoked(store, client=_OTHER) == {
            "access_token": False,
            "refresh_token": False,
            "authorization_code": False,
            "device_code": False,
        }


async def test_revoking_for_a_client_that_was_never_registered_is_refused(
    tmp_path: Path,
) -> None:
    async with stored(tmp_path) as database:
        store = _Store(database)

        with pytest.raises(InvalidArgumentError) as refused:
            await store.revoker.revoke_credentials_for_client(client_model("never-stored"))

        assert "never-stored" in str(refused.value)


async def test_it_touches_no_access_token_where_none_is_persisted(tmp_path: Path) -> None:
    async with stored(tmp_path, orm_driver(persist_access_token=False)) as database:
        store = _Store(database, persist_access_token=False)
        await store.clients.save(client_model())
        await _issued(store)

        await store.revoker.revoke_credentials_for_user(SecurityUser("user-1"))

        assert await _revoked(store) == {
            "access_token": None,
            "refresh_token": False,
            "authorization_code": True,
            "device_code": True,
        }


async def test_it_touches_no_device_code_without_the_device_flow(tmp_path: Path) -> None:
    async with stored(tmp_path, orm_driver(enable_device_code_grant=False)) as database:
        store = _Store(database, enable_device_code_grant=False)
        await store.clients.save(client_model())
        stored_client = await store.clients.find("client-1")
        assert stored_client is not None
        token = access_token_model("at-1", LATER, stored_client)
        await store.access_tokens.save(token)
        await store.authorization_codes.save(
            authorization_code_model("ac-1", LATER, stored_client),
        )

        await store.revoker.revoke_credentials_for_user(SecurityUser("user-1"))

        found = await store.access_tokens.find("at-1")
        code = await store.authorization_codes.find("ac-1")
        assert found is not None
        assert found.is_revoked() is True
        assert code is not None
        assert code.is_revoked() is True
