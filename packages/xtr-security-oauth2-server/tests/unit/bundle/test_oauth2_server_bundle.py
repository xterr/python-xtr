"""The bundle builds a working server, every service of it resolving."""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel, unit_of_work

from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.controller.authorization_controller import AuthorizationController
from xtr_security_oauth2_server.controller.device_code_controller import DeviceCodeController
from xtr_security_oauth2_server.controller.introspection_controller import (
    IntrospectionController,
)
from xtr_security_oauth2_server.controller.jwks_controller import JwksController
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.controller.revocation_controller import RevocationController
from xtr_security_oauth2_server.controller.token_controller import TokenController
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
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.oauth2_grants import OAuth2Grants
from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
    AccessTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.client_repository_interface import (
    ClientRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.device_code_repository_interface import (
    DeviceCodeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.scope_repository_interface import (
    ScopeRepositoryInterface,
)
from xtr_security_oauth2_server.repositories.user_repository_interface import (
    UserRepositoryInterface,
)
from xtr_security_oauth2_server.resource_server import ResourceServer
from xtr_security_oauth2_server.token_server import TokenServer

pytestmark = pytest.mark.anyio

#: Every singleton the bundle registers that an endpoint or a grant reaches
#: through. Resolving each is what proves the wiring: a constructor the
#: container cannot read, or an interface nothing was aliased to, fails here
#: rather than on the first request.
WIRED = (
    AuthorizationServer,
    TokenServer,
    ResourceServer,
    AccessTokenRepositoryInterface,
    AuthCodeRepositoryInterface,
    ClientRepositoryInterface,
    DeviceCodeRepositoryInterface,
    RefreshTokenRepositoryInterface,
    ScopeRepositoryInterface,
    UserRepositoryInterface,
    AccessTokenManagerInterface,
    AuthorizationCodeManagerInterface,
    ClientManagerInterface,
    DeviceCodeManagerInterface,
    RefreshTokenManagerInterface,
    ScopeManagerInterface,
    TokenController,
    DeviceCodeController,
    RevocationController,
    IntrospectionController,
    MetadataController,
    JwksController,
)

#: The one controller that is per-request rather than shared: it reads the
#: resource owner off the request through the firewall's own scoped service, so
#: it is built inside a unit of work and nowhere else.
SCOPED = (AuthorizationController,)


def _service_id(service: type) -> str:
    """Name a parametrised case after the service it resolves."""
    return service.__name__


def _configured() -> Kernel:
    """Return a kernel of the in-memory application, fully described."""
    return Kernel(
        "tests.fixtures.oauth2_server_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
        concurrent_scoped_access=True,
    )


async def test_a_described_deployment_builds_and_boots() -> None:
    async with await _configured().boot() as booted:
        assert booted.container is not None


@pytest.mark.parametrize("service", WIRED, ids=_service_id)
async def test_every_registered_service_resolves(service: type) -> None:
    async with await _configured().boot() as booted:
        assert await booted.container.get(service) is not None


@pytest.mark.parametrize("service", SCOPED, ids=_service_id)
async def test_every_per_request_service_resolves_inside_a_unit_of_work(service: type) -> None:
    async with await _configured().boot() as booted, unit_of_work(booted.container) as scoped:
        assert await scoped.get(service) is not None


async def test_every_enabled_grant_is_run_by_the_authorization_server() -> None:
    async with await _configured().boot() as booted:
        server = await booted.container.get(AuthorizationServer)

    running = repr(server)
    for identifier in (
        OAuth2Grants.AUTHORIZATION_CODE,
        OAuth2Grants.CLIENT_CREDENTIALS,
        OAuth2Grants.REFRESH_TOKEN,
        OAuth2Grants.DEVICE_CODE,
        OAuth2Grants.PASSWORD,
        OAuth2Grants.IMPLICIT,
    ):
        assert identifier in running
