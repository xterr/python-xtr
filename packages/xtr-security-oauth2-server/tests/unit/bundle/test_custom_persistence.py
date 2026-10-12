"""An application answering for its own stores, and one that forgot to register them."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel

from tests.fixtures.oauth2_custom_app.stores import (
    AccessTokenStore,
    AuthorizationCodeStore,
    ClientStore,
    CredentialsRevoker,
    DeviceCodeStore,
    RefreshTokenStore,
)
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.exception import InvalidConfigurationError
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
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

pytestmark = pytest.mark.anyio

#: Each interface the bundle points at a named store, with the store named.
NAMED: tuple[tuple[type[object], type[object]], ...] = (
    (AccessTokenManagerInterface, AccessTokenStore),
    (AuthorizationCodeManagerInterface, AuthorizationCodeStore),
    (ClientManagerInterface, ClientStore),
    (DeviceCodeManagerInterface, DeviceCodeStore),
    (RefreshTokenManagerInterface, RefreshTokenStore),
    (CredentialsRevokerInterface, CredentialsRevoker),
)


def _case(pair: tuple[type[object], type[object]]) -> str:
    return pair[0].__name__


def _custom() -> Kernel:
    """Return a kernel of the application that registers all six stores."""
    return Kernel(
        "tests.fixtures.oauth2_custom_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )


def _missing() -> Kernel:
    """Return a kernel of the application that registers none of them."""
    return Kernel(
        "tests.fixtures.oauth2_custom_missing_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )


@pytest.mark.parametrize("pair", NAMED, ids=_case)
async def test_every_interface_reaches_the_store_the_application_named(
    pair: tuple[type[object], type[object]],
) -> None:
    interface, store = pair

    async with await _custom().boot() as booted:
        resolved = await booted.container.get(interface)

    assert isinstance(resolved, store)


async def test_the_named_client_store_is_what_a_client_is_registered_through() -> None:
    async with await _custom().boot() as booted:
        clients = await booted.container.get(ClientManagerInterface)

        await clients.save(Client("A client", "named-store-client", None))
        found = await clients.find("named-store-client")

        assert found is not None
        assert found.get_identifier() == "named-store-client"


def test_naming_a_store_nothing_registered_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _missing().build()

    assert "persistence.custom" in str(refused.value)


def test_the_refusal_names_every_store_that_is_missing() -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _missing().build()

    message = str(refused.value)
    for option in (
        "persistence.custom.access_token_manager",
        "persistence.custom.authorization_code_manager",
        "persistence.custom.client_manager",
        "persistence.custom.refresh_token_manager",
        "persistence.custom.device_code_manager",
        "persistence.custom.credentials_revoker",
    ):
        assert option in message


def test_the_refusal_names_the_class_it_could_not_find() -> None:
    with pytest.raises(InvalidConfigurationError, match=r"ApplicationClientStore"):
        _ = _missing().build()
