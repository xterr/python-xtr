"""An issuer a deployment reads from its environment, directly or through a parameter.

Each deployment sets its own origin, so the issuer is commonly
``env("OAUTH2_SERVER_ISSUER")`` or a ``%parameter%`` holding one. Neither has a
value while the container is built: the variable is read where the issuer is
used, and checked there with the refusal a literal gets when it is written.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server_core.token_server import TokenServer

from tests.fixtures.oauth2_env_issuer_app.config import ISSUER_VARIABLE
from tests.support.served import (
    claims_of,
    client_credentials_token,
    json_of,
    served_application,
    serving,
    text_field,
)
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.exception import InvalidConfigurationError

pytestmark = pytest.mark.anyio

#: The deployments reading the issuer from the variable: one directly, one
#: through a parameter.
APPS = (
    "tests.fixtures.oauth2_env_issuer_app",
    "tests.fixtures.oauth2_parameter_issuer_app",
)

#: Every service the issuer is read by.
ISSUER_READERS = (MetadataController, AuthorizationServer, TokenServer, BearerTokenValidator)

#: The origin the variable names when it is set to one.
ISSUER = "https://authorization.env.test"

METADATA_PATH = "/.well-known/oauth-authorization-server"


def _app_id(app: str) -> str:
    """Name a parametrised case after the deployment it builds."""
    return app.rsplit(".", 1)[-1]


def _service_id(service: type) -> str:
    """Name a parametrised case after the service it asks for."""
    return service.__name__


def _kernel(app: str, issuer: str) -> Kernel:
    """Return a kernel of ``app``, with the issuer variable set to ``issuer``."""
    return Kernel(
        app,
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
        concurrent_scoped_access=True,
        resources=(app, "tests.support.default_routes"),
        environ={ISSUER_VARIABLE: issuer},
    )


@pytest.mark.parametrize("app", APPS, ids=_app_id)
async def test_the_description_names_the_issuer_the_variable_holds(app: str) -> None:
    async with serving(served_application(_kernel(app, ISSUER))) as client:
        document = json_of(await client.get(METADATA_PATH))

    assert text_field(document, "issuer") == ISSUER
    assert text_field(document, "token_endpoint") == f"{ISSUER}/token"


@pytest.mark.parametrize("app", APPS, ids=_app_id)
async def test_an_issued_token_claims_the_issuer_the_variable_holds(app: str) -> None:
    async with serving(served_application(_kernel(app, ISSUER))) as client:
        token = await client_credentials_token(client)

    assert claims_of(token)["iss"] == ISSUER


@pytest.mark.parametrize("service", ISSUER_READERS, ids=_service_id)
@pytest.mark.parametrize("app", APPS, ids=_app_id)
async def test_a_variable_that_is_not_an_origin_is_refused_where_the_issuer_is_used(
    app: str,
    service: type[object],
) -> None:
    async with await _kernel(app, "https://x.example/path").boot() as booted:
        with pytest.raises(ServiceResolutionError) as reported:
            _ = await booted.container.get(service)

    refusal = reported.value.__cause__
    assert isinstance(refusal, InvalidConfigurationError)
    assert "authorization_server.issuer is 'https://x.example/path'" in str(refusal)
    assert "config/packages/oauth2_server.py" in str(refusal)


async def test_a_parameter_written_as_it_stands_is_refused_when_the_configuration_resolves() -> (
    None
):
    # Known before the bundle loads, so there is no reason to wait for a service.
    kernel = Kernel(
        "tests.fixtures.oauth2_bad_parameter_issuer_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )

    with pytest.raises(InvalidConfigurationError, match=r"authorization_server\.issuer"):
        _ = await kernel.boot()
