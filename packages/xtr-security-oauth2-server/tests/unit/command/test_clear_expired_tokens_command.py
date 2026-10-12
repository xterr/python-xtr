"""``oauth2-server:clear-expired-tokens`` sweeps what this server issued and outlived."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import pytest
from xtr_console import CommandTester, ExitCode

from tests.support.console import console_kernel, running
from tests.support.models import (
    access_token_model,
    authorization_code_model,
    device_code_model,
    refresh_token_model,
)
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

_COMMAND = "oauth2-server:clear-expired-tokens"

#: Long past, so every credential stamped with it has certainly expired.
_SPENT: Final = datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC)

#: Long ahead, so every credential stamped with it certainly has not.
_LIVE: Final = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)

#: The deployment running no device flow, so a whole sweep leaves device codes alone.
_NO_DEVICE_FLOW_APP: Final = "tests.fixtures.oauth2_env_app"


async def _seed(container: ContainerInterface) -> None:
    """Store one expired and one live credential of every kind."""
    access_tokens = await container.get(AccessTokenManagerInterface)
    await access_tokens.save(access_token_model("at-spent", _SPENT))
    await access_tokens.save(access_token_model("at-live", _LIVE))
    refresh_tokens = await container.get(RefreshTokenManagerInterface)
    await refresh_tokens.save(refresh_token_model("rt-spent", _SPENT))
    await refresh_tokens.save(refresh_token_model("rt-live", _LIVE))
    codes = await container.get(AuthorizationCodeManagerInterface)
    await codes.save(authorization_code_model("ac-spent", _SPENT))
    await codes.save(authorization_code_model("ac-live", _LIVE))
    device_codes = await container.get(DeviceCodeManagerInterface)
    await device_codes.save(device_code_model("dc-spent", _SPENT, "BCDFGHJK"))
    await device_codes.save(device_code_model("dc-live", _LIVE, "LMNPQRST"))


async def _remaining(container: ContainerInterface) -> set[str]:
    """Return the identifiers of every credential still stored."""
    access_tokens = await container.get(AccessTokenManagerInterface)
    refresh_tokens = await container.get(RefreshTokenManagerInterface)
    codes = await container.get(AuthorizationCodeManagerInterface)
    device_codes = await container.get(DeviceCodeManagerInterface)
    found = [
        await access_tokens.find("at-spent"),
        await access_tokens.find("at-live"),
        await refresh_tokens.find("rt-spent"),
        await refresh_tokens.find("rt-live"),
        await codes.find("ac-spent"),
        await codes.find("ac-live"),
        await device_codes.find("dc-spent"),
        await device_codes.find("dc-live"),
    ]

    return {one.get_identifier() for one in found if one is not None}


@pytest.fixture
async def console() -> AsyncIterator[tuple[CommandTester, ContainerInterface]]:
    """Seed every store, then hand over the command and the container."""
    async with running(console_kernel()) as (application, container):
        await _seed(container)
        yield CommandTester(application, _COMMAND, width=200), container


async def test_naming_no_store_sweeps_every_one_of_them(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, container = console

    code = await tester.execute()

    assert code == ExitCode.SUCCESS
    assert "Cleared 1 expired access token." in tester.display
    assert "Cleared 1 expired refresh token." in tester.display
    assert "Cleared 1 expired auth code." in tester.display
    assert "Cleared 1 expired device code." in tester.display
    assert await _remaining(container) == {"at-live", "rt-live", "ac-live", "dc-live"}


@pytest.mark.parametrize(
    ("option", "kind", "swept"),
    [
        ("--access-tokens", "access token", "at-spent"),
        ("--refresh-tokens", "refresh token", "rt-spent"),
        ("--auth-codes", "auth code", "ac-spent"),
        ("--device-codes", "device code", "dc-spent"),
    ],
)
async def test_naming_one_store_sweeps_only_that_one(
    console: tuple[CommandTester, ContainerInterface],
    option: str,
    kind: str,
    swept: str,
) -> None:
    tester, container = console

    code = await tester.execute([option])

    assert code == ExitCode.SUCCESS
    assert f"Cleared 1 expired {kind}." in tester.display
    remaining = await _remaining(container)
    assert swept not in remaining
    assert len(remaining) == 7


@pytest.mark.parametrize(
    ("alias", "kind", "swept"),
    [
        ("-a", "access token", "at-spent"),
        ("-r", "refresh token", "rt-spent"),
        ("-c", "auth code", "ac-spent"),
        ("-dc", "device code", "dc-spent"),
    ],
)
async def test_a_store_can_be_named_by_its_short_alias(
    console: tuple[CommandTester, ContainerInterface],
    alias: str,
    kind: str,
    swept: str,
) -> None:
    tester, container = console

    code = await tester.execute([alias])

    assert code == ExitCode.SUCCESS
    assert f"Cleared 1 expired {kind}." in tester.display
    assert swept not in await _remaining(container)


async def test_an_empty_store_is_reported_in_the_plural(
    console: tuple[CommandTester, ContainerInterface],
) -> None:
    tester, _container = console
    assert await tester.execute(["--access-tokens"]) == ExitCode.SUCCESS

    code = await tester.execute(["--access-tokens"])

    assert code == ExitCode.SUCCESS
    assert "Cleared 0 expired access tokens." in tester.display


async def test_a_whole_sweep_leaves_device_codes_alone_where_no_device_flow_runs() -> None:
    async with running(console_kernel(_NO_DEVICE_FLOW_APP)) as (application, container):
        await _seed(container)
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute()

        assert code == ExitCode.SUCCESS
        assert "device code" not in tester.display
        assert "dc-spent" in await _remaining(container)


async def test_naming_the_device_codes_sweeps_them_even_where_no_device_flow_runs() -> None:
    # How a deployment clears up after turning the flow off.
    async with running(console_kernel(_NO_DEVICE_FLOW_APP)) as (application, container):
        await _seed(container)
        tester = CommandTester(application, _COMMAND, width=200)

        code = await tester.execute(["--device-codes"])

        assert code == ExitCode.SUCCESS
        assert "Cleared 1 expired device code." in tester.display
        assert "dc-spent" not in await _remaining(container)
