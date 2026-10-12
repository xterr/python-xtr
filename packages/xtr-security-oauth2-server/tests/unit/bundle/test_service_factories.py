"""The one service of this package with a dependency that may not be there.

The authorization endpoint reports a request that arrived with no resource
owner, and logging is a peer a deployment need not run. So the parameter is
declared where the channel's logger exists and left undeclared where it does
not: nothing is handed the container to probe for one, and the endpoint is
built either way.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_logging_contracts import LoggerInterface

from xtr_security_oauth2_server.bundle import OAUTH2_SERVER_CHANNEL
from xtr_security_oauth2_server.bundle._service_factories import (
    authorization_controller_factory,
)
from xtr_security_oauth2_server.controller.authorization_controller import AuthorizationController


def test_a_deployment_that_logs_asks_for_the_logger_of_this_servers_channel() -> None:
    declared = authorization_controller_factory(OAUTH2_SERVER_CHANNEL).__annotations__

    assert declared["logger"] == Annotated[LoggerInterface, Target(OAUTH2_SERVER_CHANNEL)]


def test_a_deployment_that_logs_nothing_asks_for_no_logger() -> None:
    # A parameter nothing is registered under would be refused when the
    # endpoint is built, and the endpoint is wanted either way.
    assert "logger" not in authorization_controller_factory(None).__annotations__


def test_either_way_it_builds_the_authorization_endpoint() -> None:
    for log_channel in (OAUTH2_SERVER_CHANNEL, None):
        declared = authorization_controller_factory(log_channel).__annotations__

        assert declared["return"] is AuthorizationController
