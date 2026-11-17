"""The bundle hands the introspection and userinfo handlers the application's logger and clock."""

from __future__ import annotations

import pytest
from xtr_clock import ClockInterface
from xtr_clock.bundle import ClockBundle
from xtr_dependency_injection import Kernel
from xtr_logging.bundle import LoggingBundle
from xtr_logging_contracts import LoggerInterface
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.access_token.oauth2 import Oauth2TokenHandler
from xtr_security_http.access_token.oidc import OidcUserInfoTokenHandler
from xtr_security_http.exception import InvalidAccessTokenError

from tests.fixtures.token_handler_wiring_app.peers import ServerClientBundle
from xtr_security.bundle import SecurityBundle

pytestmark = pytest.mark.anyio


def _kernel() -> Kernel:
    return Kernel(
        "tests.fixtures.token_handler_wiring_app",
        env="test",
        bundles={
            SecurityBundle: {"all": True},
            ServerClientBundle: {"all": True},
            LoggingBundle: {"all": True},
            ClockBundle: {"all": True},
        },
    )


@pytest.mark.parametrize("qualifier", ["introspected_oauth2", "userinfo_oidc_user_info"])
async def test_the_handler_writes_to_the_application_logger(qualifier: str) -> None:
    # Otherwise the failures its server's answers explain are written nowhere.
    async with await _kernel().boot() as booted:
        handler = await booted.container.get(AccessTokenHandlerInterface, qualifier)
        logger = await booted.container.get(LoggerInterface)

        with pytest.raises(InvalidAccessTokenError):
            _ = await handler.get_user_badge_from("a-token")

    assert isinstance(handler, (Oauth2TokenHandler, OidcUserInfoTokenHandler))
    assert handler._logger is logger


async def test_the_introspecting_handler_reads_the_application_clock() -> None:
    async with await _kernel().boot() as booted:
        handler = await booted.container.get(AccessTokenHandlerInterface, "introspected_oauth2")
        clock = await booted.container.get(ClockInterface)

    assert isinstance(handler, Oauth2TokenHandler)
    assert handler._clock is clock
