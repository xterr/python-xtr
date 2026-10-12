"""The same behaviour, asserted against the managers kept in a process and in a database.

A deployment swaps one set of managers for the other by changing one line of
configuration, so the two have to answer identically — not only in the shape of
their methods, which a protocol already holds them to, but in what they do: the
boundary at which something counts as expired, what a second revocation
reports, what a listing narrowed by nothing holds, and what one narrowed by two
values of a kind holds. Every assertion below runs twice, once against each
implementation, and the stored one runs against a real SQLite file.

A client handed to a stored manager has to be one its session knows, which is
why the credential fixtures hand out a client along with the manager: that is
what a request has too, since the client is read through the same session.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock

from tests.support.dispatcher import RecordingEventDispatcher
from tests.support.models import (
    EARLIER,
    LATER,
    NOW,
    access_token_model,
    authorization_code_model,
    client_model,
    device_code_model,
    refresh_token_model,
)
from tests.support.orm import CONNECTION, connections_of, registered, stored
from xtr_security_oauth2_server.manager import in_memory, orm
from xtr_security_oauth2_server.manager.client_filter import ClientFilter
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from contextlib import AbstractAsyncContextManager
    from pathlib import Path
    from typing import TypeAlias

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
    from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
        RefreshTokenManagerInterface,
    )
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

    OpenClients: TypeAlias = Callable[[Path], AbstractAsyncContextManager[ClientManagerInterface]]
    OpenAccessTokens: TypeAlias = Callable[
        [Path], AbstractAsyncContextManager[tuple[AccessTokenManagerInterface, ClientInterface]]
    ]
    OpenAuthorizationCodes: TypeAlias = Callable[
        [Path],
        AbstractAsyncContextManager[tuple[AuthorizationCodeManagerInterface, ClientInterface]],
    ]
    OpenRefreshTokens: TypeAlias = Callable[
        [Path], AbstractAsyncContextManager[RefreshTokenManagerInterface]
    ]
    OpenDeviceCodes: TypeAlias = Callable[
        [Path], AbstractAsyncContextManager[tuple[DeviceCodeManagerInterface, ClientInterface]]
    ]

pytestmark = pytest.mark.anyio


@asynccontextmanager
async def _held_clients(tmp_path: Path) -> AsyncGenerator[ClientManagerInterface, None]:
    del tmp_path
    yield in_memory.ClientManager(RecordingEventDispatcher())


@asynccontextmanager
async def _stored_clients(tmp_path: Path) -> AsyncGenerator[ClientManagerInterface, None]:
    async with stored(tmp_path) as database:
        yield orm.ClientManager(
            connections_of(database.session()),
            CONNECTION,
            RecordingEventDispatcher(),
            Client,
        )


@asynccontextmanager
async def _held_access_tokens(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AccessTokenManagerInterface, ClientInterface], None]:
    del tmp_path
    yield in_memory.AccessTokenManager(MockClock(NOW)), client_model()


@asynccontextmanager
async def _stored_access_tokens(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AccessTokenManagerInterface, ClientInterface], None]:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = orm.AccessTokenManager(
            connections_of(session),
            CONNECTION,
            MockClock(NOW),
            True,
        )
        yield manager, client


@asynccontextmanager
async def _held_authorization_codes(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AuthorizationCodeManagerInterface, ClientInterface], None]:
    del tmp_path
    yield in_memory.AuthorizationCodeManager(MockClock(NOW)), client_model()


@asynccontextmanager
async def _stored_authorization_codes(
    tmp_path: Path,
) -> AsyncGenerator[tuple[AuthorizationCodeManagerInterface, ClientInterface], None]:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        manager = orm.AuthorizationCodeManager(
            connections_of(session),
            CONNECTION,
            MockClock(NOW),
        )
        yield manager, client


@asynccontextmanager
async def _held_refresh_tokens(
    tmp_path: Path,
) -> AsyncGenerator[RefreshTokenManagerInterface, None]:
    del tmp_path
    yield in_memory.RefreshTokenManager(MockClock(NOW))


@asynccontextmanager
async def _stored_refresh_tokens(
    tmp_path: Path,
) -> AsyncGenerator[RefreshTokenManagerInterface, None]:
    async with stored(tmp_path) as database:
        yield orm.RefreshTokenManager(
            connections_of(database.session()),
            CONNECTION,
            MockClock(NOW),
        )


@asynccontextmanager
async def _held_device_codes(
    tmp_path: Path,
) -> AsyncGenerator[tuple[DeviceCodeManagerInterface, ClientInterface], None]:
    del tmp_path
    yield in_memory.DeviceCodeManager(MockClock(NOW)), client_model()


@asynccontextmanager
async def _stored_device_codes(
    tmp_path: Path,
) -> AsyncGenerator[tuple[DeviceCodeManagerInterface, ClientInterface], None]:
    async with stored(tmp_path) as database:
        session = database.session()
        client = await registered(session)
        yield orm.DeviceCodeManager(connections_of(session), CONNECTION, MockClock(NOW)), client


_CLIENTS = [_held_clients, _stored_clients]
_ACCESS_TOKENS = [_held_access_tokens, _stored_access_tokens]
_AUTHORIZATION_CODES = [_held_authorization_codes, _stored_authorization_codes]
_REFRESH_TOKENS = [_held_refresh_tokens, _stored_refresh_tokens]
_DEVICE_CODES = [_held_device_codes, _stored_device_codes]


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_client_is_found_under_the_identifier_it_was_saved_with(
    tmp_path: Path, open_clients: OpenClients
) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model())
        found = await manager.find("client-1")

        assert found is not None
        assert found.get_name() == "Test client"


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_an_unknown_client_is_not_found(tmp_path: Path, open_clients: OpenClients) -> None:
    async with open_clients(tmp_path) as manager:
        assert await manager.find("nope") is None


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_client_that_was_removed_is_gone(tmp_path: Path, open_clients: OpenClients) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model())
        found = await manager.find("client-1")
        assert found is not None

        await manager.remove(found)

        assert await manager.find("client-1") is None


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_listing_narrowed_by_nothing_holds_every_client(
    tmp_path: Path, open_clients: OpenClients
) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model("one"))
        await manager.save(client_model("two"))

        assert len(await manager.list(None)) == 2
        assert len(await manager.list(ClientFilter.create())) == 2


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_listing_holds_the_clients_meeting_every_kind_of_criterion(
    tmp_path: Path, open_clients: OpenClients
) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model("both", grants=["refresh_token"], scopes=["read"]))
        await manager.save(client_model("grant-only", grants=["refresh_token"]))
        await manager.save(client_model("open"))

        listed = await manager.list(
            ClientFilter.create()
            .add_grant_criteria(Grant("refresh_token"))
            .add_scope_criteria(Scope("read")),
        )

        assert [client.get_identifier() for client in listed] == ["both"]


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_listing_holds_the_clients_holding_every_value_of_a_kind(
    tmp_path: Path, open_clients: OpenClients
) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model("both", grants=["password", "implicit"]))
        await manager.save(client_model("one-of-them", grants=["password"]))

        listed = await manager.list(
            ClientFilter.create().add_grant_criteria(Grant("password"), Grant("implicit")),
        )

        assert [client.get_identifier() for client in listed] == ["both"]


@pytest.mark.parametrize("open_clients", _CLIENTS)
async def test_a_client_holding_nothing_of_a_named_kind_is_left_out_of_a_listing(
    tmp_path: Path, open_clients: OpenClients
) -> None:
    async with open_clients(tmp_path) as manager:
        await manager.save(client_model("open"))

        listed = await manager.list(ClientFilter.create().add_grant_criteria(Grant("implicit")))

        assert listed == ()


@pytest.mark.parametrize("open_access_tokens", _ACCESS_TOKENS)
async def test_an_access_token_is_found_with_the_scopes_it_was_granted(
    tmp_path: Path, open_access_tokens: OpenAccessTokens
) -> None:
    async with open_access_tokens(tmp_path) as (manager, client):
        await manager.save(access_token_model(client=client, scopes=["read"]))
        found = await manager.find("at-1")

        assert found is not None
        assert found.get_scopes() == (Scope("read"),)
        assert found.get_expiry() == LATER
        assert found.is_revoked() is False


@pytest.mark.parametrize("open_access_tokens", _ACCESS_TOKENS)
async def test_an_unknown_access_token_is_not_found(
    tmp_path: Path, open_access_tokens: OpenAccessTokens
) -> None:
    async with open_access_tokens(tmp_path) as (manager, _):
        assert await manager.find("nope") is None


@pytest.mark.parametrize("open_access_tokens", _ACCESS_TOKENS)
async def test_saving_an_access_token_again_replaces_what_was_stored(
    tmp_path: Path, open_access_tokens: OpenAccessTokens
) -> None:
    async with open_access_tokens(tmp_path) as (manager, client):
        token = access_token_model(client=client)
        await manager.save(token)

        await manager.save(token.revoke())
        found = await manager.find("at-1")

        assert found is not None
        assert found.is_revoked() is True


@pytest.mark.parametrize("open_access_tokens", _ACCESS_TOKENS)
async def test_the_expired_access_tokens_are_swept_and_counted(
    tmp_path: Path, open_access_tokens: OpenAccessTokens
) -> None:
    async with open_access_tokens(tmp_path) as (manager, client):
        await manager.save(access_token_model("expired", EARLIER, client))
        await manager.save(access_token_model("alive", LATER, client))

        cleared = await manager.clear_expired()

        assert cleared == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


@pytest.mark.parametrize("open_access_tokens", _ACCESS_TOKENS)
async def test_an_access_token_expiring_this_very_instant_is_kept(
    tmp_path: Path, open_access_tokens: OpenAccessTokens
) -> None:
    async with open_access_tokens(tmp_path) as (manager, client):
        await manager.save(access_token_model("on-the-boundary", NOW, client))

        cleared = await manager.clear_expired()

        assert cleared == 0
        assert await manager.find("on-the-boundary") is not None


@pytest.mark.parametrize("open_codes", _AUTHORIZATION_CODES)
async def test_an_authorization_code_is_found_with_what_was_consented_to(
    tmp_path: Path, open_codes: OpenAuthorizationCodes
) -> None:
    async with open_codes(tmp_path) as (manager, client):
        await manager.save(authorization_code_model(client=client, scopes=["read"]))
        found = await manager.find("ac-1")

        assert found is not None
        assert found.get_scopes() == (Scope("read"),)
        assert found.get_user_identifier() == "user-1"


@pytest.mark.parametrize("open_codes", _AUTHORIZATION_CODES)
async def test_an_unknown_authorization_code_is_not_found(
    tmp_path: Path, open_codes: OpenAuthorizationCodes
) -> None:
    async with open_codes(tmp_path) as (manager, _):
        assert await manager.find("nope") is None


@pytest.mark.parametrize("open_codes", _AUTHORIZATION_CODES)
async def test_the_expired_authorization_codes_are_swept_and_counted(
    tmp_path: Path, open_codes: OpenAuthorizationCodes
) -> None:
    async with open_codes(tmp_path) as (manager, client):
        await manager.save(authorization_code_model("expired", EARLIER, client))
        await manager.save(authorization_code_model("alive", LATER, client))

        cleared = await manager.clear_expired()

        assert cleared == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_a_refresh_token_is_found_under_the_identifier_it_was_saved_with(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        await manager.save(refresh_token_model())
        found = await manager.find("rt-1")

        assert found is not None
        assert found.get_expiry() == LATER
        assert found.is_revoked() is False


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_an_unknown_refresh_token_is_not_found(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        assert await manager.find("nope") is None


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_exactly_one_caller_is_told_it_revoked_a_refresh_token(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        await manager.save(refresh_token_model())

        assert await manager.revoke("rt-1") is True
        assert await manager.revoke("rt-1") is False


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_revoking_an_unknown_refresh_token_revoked_nothing(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        assert await manager.revoke("nope") is False


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_a_revoked_refresh_token_reads_back_revoked(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        await manager.save(refresh_token_model())

        _ = await manager.revoke("rt-1")
        found = await manager.find("rt-1")

        assert found is not None
        assert found.is_revoked() is True


@pytest.mark.parametrize("open_refresh_tokens", _REFRESH_TOKENS)
async def test_the_expired_refresh_tokens_are_swept_and_counted(
    tmp_path: Path, open_refresh_tokens: OpenRefreshTokens
) -> None:
    async with open_refresh_tokens(tmp_path) as manager:
        await manager.save(refresh_token_model("expired", EARLIER))
        await manager.save(refresh_token_model("alive", LATER))

        cleared = await manager.clear_expired()

        assert cleared == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None


@pytest.mark.parametrize("open_device_codes", _DEVICE_CODES)
async def test_a_device_code_is_found_by_either_of_its_two_codes(
    tmp_path: Path, open_device_codes: OpenDeviceCodes
) -> None:
    async with open_device_codes(tmp_path) as (manager, client):
        await manager.save(device_code_model(client=client))

        by_identifier = await manager.find("dc-1")
        by_user_code = await manager.find_by_user_code("BCDFGHJK")

        assert by_identifier is not None
        assert by_user_code is not None
        assert by_user_code.get_identifier() == "dc-1"


@pytest.mark.parametrize("open_device_codes", _DEVICE_CODES)
async def test_an_unknown_device_code_is_not_found_by_either_code(
    tmp_path: Path, open_device_codes: OpenDeviceCodes
) -> None:
    async with open_device_codes(tmp_path) as (manager, _):
        assert await manager.find("nope") is None
        assert await manager.find_by_user_code("ZZZZZZZZ") is None


@pytest.mark.parametrize("open_device_codes", _DEVICE_CODES)
async def test_the_expired_device_codes_are_swept_and_counted(
    tmp_path: Path, open_device_codes: OpenDeviceCodes
) -> None:
    async with open_device_codes(tmp_path) as (manager, client):
        await manager.save(device_code_model("expired", EARLIER, "AAAAAAAA", client))
        await manager.save(device_code_model("alive", LATER, "BBBBBBBB", client))

        cleared = await manager.clear_expired()

        assert cleared == 1
        assert await manager.find("expired") is None
        assert await manager.find("alive") is not None
