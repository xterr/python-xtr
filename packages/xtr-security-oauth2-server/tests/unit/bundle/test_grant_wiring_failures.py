"""Two deployment mistakes about grants, each refused rather than served.

A server with no flow could issue nothing, and two flows answering one name
would leave whichever was registered last. Neither is a configuration a
deployment should be able to run.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.exception import InvalidConfigurationError

pytestmark = pytest.mark.anyio


def _kernel(app_module: str) -> Kernel:
    """Return a kernel of ``app_module``, running this package's bundle."""
    return Kernel(
        app_module,
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
        concurrent_scoped_access=True,
    )


def test_a_deployment_running_no_flow_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _kernel("tests.fixtures.oauth2_no_grant_app").build()

    assert "runs no OAuth 2.0 grant" in str(refused.value)


def test_the_refusal_names_the_settings_a_flow_is_turned_on_with() -> None:
    with pytest.raises(InvalidConfigurationError) as refused:
        _ = _kernel("tests.fixtures.oauth2_no_grant_app").build()

    message = str(refused.value)
    for setting in (
        "enable_client_credentials_grant",
        "enable_auth_code_grant",
        "enable_refresh_token_grant",
        "enable_device_code_grant",
    ):
        assert setting in message


async def test_two_grants_answering_one_name_are_refused_naming_both() -> None:
    # The identifier only exists on a built grant, so this is settled where the
    # server is assembled rather than while the container is compiled; the
    # container reports what a factory raised as a resolution failure, keeping
    # the refusal as its cause.
    async with await _kernel("tests.fixtures.oauth2_clashing_grant_app").boot() as booted:
        with pytest.raises(ServiceResolutionError) as refused:
            _ = await booted.container.get(AuthorizationServer)

    assert isinstance(refused.value.__cause__, InvalidConfigurationError)
    message = str(refused.value)
    assert "client_credentials" in message
    assert "ClashingGrant" in message
    assert "ClientCredentialsGrant" in message


async def test_a_contributed_grant_is_built_and_collected() -> None:
    # The other half of the same fixture: being nominally a grant was enough
    # for the container to tag it and the pass to hand it over, which is only
    # possible if its inherited constructor can be read at runtime.
    async with await _kernel("tests.fixtures.oauth2_clashing_grant_app").boot() as booted:
        with pytest.raises(ServiceResolutionError) as refused:
            _ = await booted.container.get(AuthorizationServer)

    # It reached the server, which is what the clash proves.
    assert "ClashingGrant" in str(refused.value)
