"""``oauth2-server:list-clients`` shows the registrations, with every secret masked."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import CommandTester, ExitCode

from tests.support.console import console_kernel, running
from tests.support.models import client_model
from xtr_security_oauth2_server.command.list_clients_command import COLUMNS
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:list-clients"

#: The hash of the secret the registered clients hold, which must never be shown.
_STORED_HASH = "a-stored-secret-hash"


@pytest.fixture
async def console() -> AsyncIterator[tuple[CommandTester, ContainerInterface]]:
    """Hand over the command and the container that built it."""
    async with running(console_kernel()) as (application, container):
        yield CommandTester(application, _COMMAND, width=200), container


async def _register(
    container: ContainerInterface,
    identifier: str,
    secret: str | None = _STORED_HASH,
    *,
    scopes: tuple[str, ...] = (),
    grants: tuple[str, ...] = (),
    redirect_uris: tuple[str, ...] = (),
) -> None:
    """Register one client the way an administration screen would."""
    clients = await container.get(ClientManagerInterface)
    await clients.save(
        client_model(
            identifier,
            secret,
            "client",
            scopes=scopes,
            grants=grants,
            redirect_uris=redirect_uris,
        ),
    )


async def test_an_empty_store_lists_the_headers_and_no_row(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await tester.execute()

    assert code == ExitCode.SUCCESS
    for column in COLUMNS:
        assert column in tester.display


async def test_a_confidential_client_has_its_secret_masked(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(container, "foobar", scopes=("rock",))

    code = await tester.execute()

    assert code == ExitCode.SUCCESS
    assert "foobar" in tester.display
    assert "rock" in tester.display
    assert "****" in tester.display
    # Not even the stored hash: a hash on a terminal is a guessing target.
    assert _STORED_HASH not in tester.display


async def test_a_client_holding_no_secret_is_shown_as_public(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(container, "foobar", None, scopes=("rock",))

    code = await tester.execute()

    assert code == ExitCode.SUCCESS
    assert "(public)" in tester.display
    assert "****" not in tester.display


async def test_no_option_reveals_a_stored_secret(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(container, "foobar")

    # No option shows a stored secret, so asking for one is not a command line
    # this listing answers to.
    code = await tester.execute(["--reveal-secret"])

    assert code == ExitCode.INVALID
    assert _STORED_HASH not in tester.display


async def test_only_the_columns_named_are_shown_in_the_order_named(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(
        container,
        "foobar",
        scopes=("client-scope-1", "client-scope-2"),
        redirect_uris=("https://client.test/cb",),
    )

    code = await tester.execute(["--columns", "scope", "--columns", "identifier"])

    assert code == ExitCode.SUCCESS
    headers = next(line for line in tester.display.splitlines() if "identifier" in line)
    assert headers.index("scope") < headers.index("identifier")
    assert "client-scope-1, client-scope-2" in tester.display
    assert "name" not in headers
    assert "https://client.test/cb" not in tester.display


async def test_a_column_name_is_read_whatever_its_case_and_spacing(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(container, "foobar", grants=("client_credentials",))

    code = await tester.execute(["--columns", " Grant Type "])

    assert code == ExitCode.SUCCESS
    assert "client_credentials" in tester.display


async def test_a_name_that_is_not_a_column_is_reported(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await tester.execute(["--columns", "secrets"])

    assert code == ExitCode.FAILURE
    assert "'secrets' is not a column of a client listing" in tester.display


async def test_a_listing_narrowed_by_scope_holds_only_the_clients_holding_it(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(container, "client-a", scopes=("client-a-scope", "other-scope-1"))
    await _register(container, "client-b", scopes=("client-b-scope", "other-scope"))
    await _register(container, "client-c", scopes=("client-c-scope", "1-other-scope"))

    code = await tester.execute(["--scope", "other-scope"])

    assert code == ExitCode.SUCCESS
    assert "client-b" in tester.display
    assert "client-a" not in tester.display
    assert "client-c" not in tester.display


async def test_a_listing_narrowed_by_grant_and_redirect_uri_takes_both(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console
    await _register(
        container,
        "client-a",
        grants=("client_credentials",),
        redirect_uris=("https://a.test/cb",),
    )
    await _register(container, "client-b", grants=("client_credentials",))

    code = await tester.execute(
        ["--grant-type", "client_credentials", "--redirect-uri", "https://a.test/cb"],
    )

    assert code == ExitCode.SUCCESS
    assert "client-a" in tester.display
    assert "client-b" not in tester.display


async def test_a_criterion_that_is_not_a_redirect_uri_is_refused(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await tester.execute(["--redirect-uri", "not a uri"])

    assert code == ExitCode.FAILURE
    assert "not a valid URI" in tester.display
