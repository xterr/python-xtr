"""``oauth2-server:create-client`` registers a client and shows its secret once."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from xtr_console import CommandTester, ExitCode
from xtr_password_hasher import PasswordHasherInterface

from tests.support.console import console_kernel, running
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from xtr_service_contracts import ContainerInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:create-client"

#: What the rendered table draws between two cells.
_CELL_BORDER = "\u2502"


@pytest.fixture
async def console() -> AsyncIterator[tuple[CommandTester, ContainerInterface]]:
    """Hand over the command and the container that built it."""
    async with running(console_kernel()) as (application, container):
        yield CommandTester(application, _COMMAND, width=200), container


async def _stored(container: ContainerInterface, identifier: str) -> ClientInterface | None:
    """Return the client the run registered, read through the shared manager."""
    clients = await container.get(ClientManagerInterface)

    return await clients.find(identifier)


async def _hasher(container: ContainerInterface) -> PasswordHasherInterface:
    """Return the hasher a client secret is kept under — this package's own."""
    return await container.get(PasswordHasherInterface, "oauth2_server")


def _printed_secret(display: str, identifier: str) -> str:
    """Return the secret the run printed beside ``identifier`` in its table."""
    for line in display.splitlines():
        cells = [cell.strip() for cell in line.split(_CELL_BORDER)]
        if len(cells) == 4 and cells[1] == identifier:
            return cells[2]
    raise AssertionError(f"no table row for {identifier} in:\n{display}")


async def _run(
    console: tuple[CommandTester, ContainerInterface],
    args: Sequence[str],
) -> int:
    tester, _container = console

    return await tester.execute(list(args))


async def test_it_registers_a_client_under_the_identifier_it_was_given(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar"])

    assert code == ExitCode.SUCCESS
    assert "New OAuth2 client created successfully." in tester.display
    assert "foobar" in tester.display
    client = await _stored(container, "foobar")
    assert client is not None
    assert client.get_name() == "A client"
    assert client.is_active()
    assert client.is_confidential()
    assert not client.is_plain_text_pkce_allowed()


async def test_a_client_given_no_identifier_is_registered_under_a_minted_one(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client"])

    assert code == ExitCode.SUCCESS
    clients = await container.get(ClientManagerInterface)
    registered = await clients.list(None)
    assert len(registered) == 1
    minted = registered[0].get_identifier()
    assert re.fullmatch(r"[0-9a-f]{32}", minted), minted
    assert minted in tester.display


async def test_the_secret_it_prints_is_the_plaintext_and_what_it_stores_is_the_hash(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar"])

    assert code == ExitCode.SUCCESS
    printed = _printed_secret(tester.display, "foobar")
    client = await _stored(container, "foobar")
    assert client is not None
    stored = client.get_secret()
    assert stored is not None
    # Never the plaintext, and the plaintext is what the table showed.
    assert stored != printed
    assert (await _hasher(container)).verify(stored, printed)


async def test_a_minted_secret_is_sixty_four_hexadecimal_characters(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await _run(console, ["A client", "foobar"])

    assert code == ExitCode.SUCCESS
    minted = _printed_secret(tester.display, "foobar")
    assert re.fullmatch(r"[0-9a-f]{64}", minted), minted


async def test_the_plaintext_secret_is_shown_once_and_nowhere_else(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    # The one place the plaintext ever exists outside whoever copies it is
    # the cell of the table below. Printed twice — echoed in a message, left
    # in a second column — it would be twice as likely to be scrolled past
    # into a terminal's history or a pipeline's log.
    tester, _container = console

    code = await _run(console, ["A client", "foobar", "a-secret-nobody-minted"])

    assert code == ExitCode.SUCCESS
    assert tester.display.count("a-secret-nobody-minted") == 1
    assert "a-secret-nobody-minted" not in tester.error_display


async def test_a_secret_it_was_given_is_the_one_stored_hashed(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    _tester, container = console

    code = await _run(console, ["A client", "foobar", "quzbaz"])

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar")
    assert client is not None
    stored = client.get_secret()
    assert stored is not None
    assert stored != "quzbaz"
    assert (await _hasher(container)).verify(stored, "quzbaz")


async def test_a_public_client_is_registered_holding_no_secret(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar test", "--public"])

    assert code == ExitCode.SUCCESS
    assert "foobar test" in tester.display
    assert "(public)" in tester.display
    client = await _stored(container, "foobar test")
    assert client is not None
    assert client.get_secret() is None
    assert not client.is_confidential()


async def test_a_public_client_with_a_secret_is_refused_and_nothing_is_registered(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar test", "quzbaz", "--public"])

    assert code == ExitCode.FAILURE
    assert "The client cannot have a secret and be public." in tester.display
    assert "foobar test" not in tester.display
    assert await _stored(container, "foobar test") is None


async def test_a_client_may_be_registered_allowed_an_unhashed_code_challenge(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    _tester, container = console

    code = await _run(console, ["A client", "foobar-123", "--allow-plain-text-pkce"])

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar-123")
    assert client is not None
    assert client.is_plain_text_pkce_allowed()


async def test_every_redirect_uri_named_is_registered(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    _tester, container = console

    code = await _run(
        console,
        [
            "A client",
            "foobar",
            "--redirect-uri",
            "https://one.test/cb",
            "--redirect-uri",
            "https://two.test/cb",
        ],
    )

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar")
    assert client is not None
    assert [str(one) for one in client.get_redirect_uris()] == [
        "https://one.test/cb",
        "https://two.test/cb",
    ]


async def test_every_grant_named_is_registered(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    _tester, container = console

    code = await _run(
        console,
        ["A client", "foobar", "--grant-type", "password", "--grant-type", "client_credentials"],
    )

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar")
    assert client is not None
    assert [str(one) for one in client.get_grants()] == ["password", "client_credentials"]


async def test_every_scope_named_is_registered(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    _tester, container = console

    code = await _run(console, ["A client", "foobar", "--scope", "read", "--scope", "write"])

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar")
    assert client is not None
    assert [str(one) for one in client.get_scopes()] == ["read", "write"]


async def test_a_client_naming_no_scope_is_given_the_configured_default_ones(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    # The listener this package ships runs as the client is stored, so a
    # registration made by this command gets the same default as one made by
    # an application's own screen.
    _tester, container = console

    code = await _run(console, ["A client", "foobar"])

    assert code == ExitCode.SUCCESS
    client = await _stored(container, "foobar")
    assert client is not None
    assert [str(one) for one in client.get_scopes()] == ["read"]


async def test_a_redirect_uri_that_is_not_one_is_refused_and_nothing_is_registered(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar", "--redirect-uri", "not a uri"])

    assert code == ExitCode.FAILURE
    assert "not a valid URI" in tester.display
    assert await _stored(container, "foobar") is None


async def test_a_grant_with_no_name_is_refused(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await _run(console, ["A client", "foobar", "--grant-type", ""])

    assert code == ExitCode.FAILURE
    assert "A grant has to be named" in tester.display
    assert await _stored(container, "foobar") is None


async def test_an_identifier_already_registered_is_refused(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    assert await _run(console, ["A client", "foobar"]) == ExitCode.SUCCESS
    tester, _container = console

    code = await _run(console, ["Another client", "foobar"])

    assert code == ExitCode.FAILURE
    assert 'OAuth2 client identified as "foobar" already exists.' in tester.display


async def test_a_taken_identifier_leaves_the_client_registered_under_it_as_it_was(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    # The one way a client's secret is replaced is being registered again
    # under another identifier: a run that names one already taken must not
    # quietly rotate the secret the client it names is authenticating with.
    _tester, container = console
    assert await _run(console, ["A client", "foobar"]) == ExitCode.SUCCESS
    first = await _stored(container, "foobar")
    assert first is not None
    held = first.get_secret()

    _code = await _run(console, ["Another client", "foobar", "a-secret-of-its-own"])

    again = await _stored(container, "foobar")
    assert again is not None
    assert again.get_name() == "A client"
    assert again.get_secret() == held
