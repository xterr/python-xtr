"""``oauth2-server:update-client`` amends a registration one change at a time."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import CommandTester, ExitCode

from tests.support.console import console_kernel, running
from tests.support.models import client_model
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:update-client"

_IDENTIFIER = "foobar"


@pytest.fixture
async def console() -> AsyncIterator[tuple[CommandTester, ContainerInterface]]:
    """Register one client, then hand over the command and the container."""
    async with running(console_kernel()) as (application, container):
        clients = await container.get(ClientManagerInterface)
        registered = client_model(_IDENTIFIER)
        _ = registered.set_redirect_uris(
            RedirectUri("https://one.test"), RedirectUri("https://two.test")
        )
        _ = registered.set_grants(Grant("one"), Grant("two"))
        _ = registered.set_scopes(Scope("one"), Scope("two"))
        await clients.save(registered)
        yield CommandTester(application, _COMMAND, width=200), container


async def _stored(container: ContainerInterface) -> ClientInterface:
    """Return the registration as it now stands."""
    clients = await container.get(ClientManagerInterface)
    client = await clients.find(_IDENTIFIER)
    assert client is not None

    return client


async def test_an_unknown_client_is_reported_and_nothing_is_amended(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await tester.execute(["nobody", "--activate"])

    assert code == ExitCode.FAILURE
    assert 'OAuth2 client identified as "nobody" does not exist.' in tester.display


async def test_redirect_uris_are_added_and_removed(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute(
        [
            _IDENTIFIER,
            "--add-redirect-uri",
            "https://three.test",
            "--add-redirect-uri",
            "https://four.test",
            "--remove-redirect-uri",
            "https://one.test",
            "--remove-redirect-uri",
            "https://five.test",
        ],
    )

    assert code == ExitCode.SUCCESS
    assert "OAuth2 client updated successfully." in tester.display
    client = await _stored(container)
    assert [str(one) for one in client.get_redirect_uris()] == [
        "https://two.test",
        "https://three.test",
        "https://four.test",
    ]


async def test_grants_are_added_and_removed(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute(
        [
            _IDENTIFIER,
            "--add-grant-type",
            "three",
            "--add-grant-type",
            "four",
            "--remove-grant-type",
            "one",
            "--remove-grant-type",
            "five",
        ],
    )

    assert code == ExitCode.SUCCESS
    client = await _stored(container)
    assert [str(one) for one in client.get_grants()] == ["two", "three", "four"]


async def test_scopes_are_added_and_removed(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute(
        [
            _IDENTIFIER,
            "--add-scope",
            "three",
            "--add-scope",
            "four",
            "--remove-scope",
            "one",
            "--remove-scope",
            "five",
        ],
    )

    assert code == ExitCode.SUCCESS
    client = await _stored(container)
    assert [str(one) for one in client.get_scopes()] == ["two", "three", "four"]


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("redirect-uri", "https://one.test"),
        ("grant-type", "one"),
        ("scope", "one"),
    ],
)
async def test_naming_one_value_to_add_and_to_remove_is_refused(
    console: tuple[CommandTester, ContainerInterface],
    option: str,
    value: str,
) -> None:
    tester, container = console

    code = await tester.execute(
        [_IDENTIFIER, f"--add-{option}", value, f"--remove-{option}", value],
    )

    assert code == ExitCode.FAILURE
    assert f'Cannot specify "{value}" in either "--add-{option}" and "--remove-{option}".' in (
        tester.display
    )
    client = await _stored(container)
    # Nothing was written: the registration still holds what it did.
    assert len(client.get_redirect_uris()) == 2
    assert len(client.get_grants()) == 2
    assert len(client.get_scopes()) == 2


async def test_a_client_is_deactivated_and_activated_again(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    assert await tester.execute([_IDENTIFIER, "--deactivate"]) == ExitCode.SUCCESS
    assert not (await _stored(container)).is_active()

    assert await tester.execute([_IDENTIFIER, "--activate"]) == ExitCode.SUCCESS
    assert (await _stored(container)).is_active()


async def test_a_run_naming_neither_leaves_the_state_alone(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    assert await tester.execute([_IDENTIFIER, "--deactivate"]) == ExitCode.SUCCESS
    assert await tester.execute([_IDENTIFIER, "--add-scope", "three"]) == ExitCode.SUCCESS

    assert not (await _stored(container)).is_active()


async def test_activating_and_deactivating_at_once_is_refused(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute([_IDENTIFIER, "--activate", "--deactivate"])

    assert code == ExitCode.FAILURE
    assert 'Cannot specify "--activate" and "--deactivate" at the same time.' in tester.display
    assert (await _stored(container)).is_active()


async def test_a_scope_with_no_name_is_refused(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console

    code = await tester.execute([_IDENTIFIER, "--add-scope", ""])

    assert code == ExitCode.FAILURE
    assert "A scope has to be named" in tester.display


async def test_removing_the_last_scope_leaves_the_default_ones_in_its_place(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    # Amending goes through the client manager, which announces every save,
    # and the listener this package ships reads a scope-less client as one
    # registered with no scopes — so taking the last scope away hands the
    # client the deployment's default scopes rather than none. The run says
    # it amended the client, which it did: the amendment is just not the one
    # the options read like. A deployment wanting a scope-less client
    # configures no default scopes.
    tester, container = console

    code = await tester.execute([_IDENTIFIER, "--remove-scope", "one", "--remove-scope", "two"])

    assert code == ExitCode.SUCCESS
    assert "OAuth2 client updated successfully." in tester.display
    assert [str(one) for one in (await _stored(container)).get_scopes()] == ["read"]
