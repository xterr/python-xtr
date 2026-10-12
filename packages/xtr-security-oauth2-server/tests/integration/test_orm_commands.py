"""Every command driven against a database, through the console that runs them.

What this proves is the one thing an in-process store cannot: a command runs
outside a request, and the stored managers ask the connection registry for *the
session of the unit of work under way* — so if a command run were not one, every
one of them would be refused before it reached a table.

That is asserted directly: the shared manager, asked outside a run, reports
there is no session; asked by a command, it reads and writes and commits, which
a second unit of work then sees.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, TypeAlias

import pytest
from xtr_console import Application, CommandTester, ExitCode
from xtr_dependency_injection import unit_of_work
from xtr_orm.exception import SessionUnavailableError

from tests.fixtures.oauth2_orm_app.config import URL_VARIABLE
from tests.support.console import console_kernel, running
from tests.support.models import access_token_model
from tests.support.orm_app import stored_tables, stored_url
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from xtr_service_contracts import ContainerInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

pytestmark = pytest.mark.anyio

Console: TypeAlias = "tuple[Application, ContainerInterface]"
"""A booted console of the stored deployment, and the container behind it."""

_APP: Final = "tests.fixtures.oauth2_orm_app"

_IDENTIFIER: Final = "a-stored-client"

#: Long past, so a credential stamped with it has certainly expired.
_SPENT: Final = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture
async def console(tmp_path: Path) -> AsyncIterator[Console]:
    """Create the stored deployment's tables, boot its console, and hand both over."""
    environ = {URL_VARIABLE: stored_url(tmp_path)}
    async with (
        stored_tables(tmp_path),
        running(console_kernel(_APP, orm=True, environ=environ)) as booted,
    ):
        yield booted


def _tester(console: Console, name: str) -> CommandTester:
    """Return a tester for the command ``name`` of the booted console."""
    application, _container = console

    return CommandTester(application, name, width=200)


async def _registered(console: Console) -> None:
    """Register the client the amending commands act on, through the command for it."""
    tester = _tester(console, "oauth2-server:create-client")

    assert await tester.execute(["A client", _IDENTIFIER]) == ExitCode.SUCCESS, tester.display


async def _read(container: ContainerInterface, identifier: str) -> ClientInterface | None:
    """Read a client in a unit of work of its own, so only committed rows show."""
    async with unit_of_work(container) as unit:
        clients = await unit.get(ClientManagerInterface)

        return await clients.find(identifier)


async def test_the_shared_manager_has_no_session_outside_a_command_run(
    console: Console,
) -> None:
    # The premise of everything below: nothing but a unit of work gives a
    # stored manager a session, and a command run is one.
    _application, container = console
    clients = await container.get(ClientManagerInterface)

    with pytest.raises(SessionUnavailableError):
        _ = await clients.find(_IDENTIFIER)


async def test_creating_a_client_writes_a_row_a_second_unit_of_work_sees(
    console: Console,
) -> None:
    _application, container = console
    tester = _tester(console, "oauth2-server:create-client")

    code = await tester.execute(["A client", _IDENTIFIER, "--scope", "read"])

    assert code == ExitCode.SUCCESS, tester.display
    stored = await _read(container, _IDENTIFIER)
    assert stored is not None
    assert stored.get_name() == "A client"
    assert [str(one) for one in stored.get_scopes()] == ["read"]


async def test_listing_reads_the_rows_a_previous_run_committed(console: Console) -> None:
    await _registered(console)
    tester = _tester(console, "oauth2-server:list-clients")

    code = await tester.execute()

    assert code == ExitCode.SUCCESS, tester.display
    assert _IDENTIFIER in tester.display
    assert "****" in tester.display


async def test_updating_a_client_commits_the_amendment(console: Console) -> None:
    _application, container = console
    await _registered(console)
    tester = _tester(console, "oauth2-server:update-client")

    code = await tester.execute([_IDENTIFIER, "--add-grant-type", "client_credentials"])

    assert code == ExitCode.SUCCESS, tester.display
    stored = await _read(container, _IDENTIFIER)
    assert stored is not None
    assert [str(one) for one in stored.get_grants()] == ["client_credentials"]


async def test_deleting_a_client_commits_the_withdrawal(console: Console) -> None:
    _application, container = console
    await _registered(console)
    tester = _tester(console, "oauth2-server:delete-client")

    code = await tester.execute([_IDENTIFIER])

    assert code == ExitCode.SUCCESS, tester.display
    assert await _read(container, _IDENTIFIER) is None


async def test_an_unknown_client_is_reported_against_a_database_too(console: Console) -> None:
    tester = _tester(console, "oauth2-server:delete-client")

    code = await tester.execute(["nobody"])

    assert code == ExitCode.FAILURE
    assert 'OAuth2 client identified as "nobody" does not exist.' in tester.display


async def test_an_identifier_already_registered_is_refused_against_a_database_too(
    console: Console,
) -> None:
    await _registered(console)
    tester = _tester(console, "oauth2-server:create-client")

    code = await tester.execute(["Another client", _IDENTIFIER])

    assert code == ExitCode.FAILURE
    assert f'OAuth2 client identified as "{_IDENTIFIER}" already exists.' in tester.display


async def test_a_refused_registration_shows_nothing_of_the_row_that_is_stored(
    console: Console,
) -> None:
    # What the store would say of a rejected INSERT carries the statement and
    # its bound values — the hash of the stored client's secret among them.
    # Nothing of that reaches a terminal: the refusal is this package's own.
    await _registered(console)
    tester = _tester(console, "oauth2-server:create-client")

    _code = await tester.execute(["Another client", _IDENTIFIER])

    printed = tester.display + tester.error_display
    assert "INSERT INTO" not in printed
    assert "parameters" not in printed
    assert "$argon2" not in printed


async def test_sweeping_deletes_the_expired_rows_and_keeps_the_rest(console: Console) -> None:
    _application, container = console
    await _registered(console)
    async with unit_of_work(container) as unit:
        clients = await unit.get(ClientManagerInterface)
        client = await clients.find(_IDENTIFIER)
        assert client is not None
        access_tokens = await unit.get(AccessTokenManagerInterface)
        await access_tokens.save(access_token_model("at-spent", _SPENT, client))
    tester = _tester(console, "oauth2-server:clear-expired-tokens")

    code = await tester.execute(["--access-tokens"])

    assert code == ExitCode.SUCCESS, tester.display
    assert "Cleared 1 expired access token." in tester.display
    async with unit_of_work(container) as unit:
        access_tokens = await unit.get(AccessTokenManagerInterface)
        assert await access_tokens.find("at-spent") is None
    # The client the token named is untouched: a sweep clears credentials.
    assert await _read(container, _IDENTIFIER) is not None


async def test_a_whole_sweep_reaches_every_store_of_the_database(console: Console) -> None:
    tester = _tester(console, "oauth2-server:clear-expired-tokens")

    code = await tester.execute()

    assert code == ExitCode.SUCCESS, tester.display
    for kind in ("access tokens", "refresh tokens", "auth codes", "device codes"):
        assert f"Cleared 0 expired {kind}." in tester.display
