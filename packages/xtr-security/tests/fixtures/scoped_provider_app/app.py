"""The served FastAPI application the scoped-provider tests drive.

Every page behind a firewall answers the user the request is authenticated
as; the guarded login page answers the error the last attempt failed with,
read the way a login page reads it, off the state the chain parked on the
request.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import FastAPI, Request
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_http_message_contracts import ServerRequestInterface
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import AuthenticationUtils, CurrentUser, SecurityRequestAttributes

from tests.fixtures.scoped_provider_app.bundles import BUNDLES

__all__ = ["app", "kernel", "serve"]


def serve(served_by: Kernel) -> FastAPI:
    """Return the fixture's pages as an application set up on ``served_by``."""
    application = FastAPI()

    @application.get("/guarded/login")
    async def guarded_login_page(
        request: Request,
        served: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        """Answer the error the last guarded login attempt failed with."""
        state = cast("dict[str, object]", request.scope["state"])
        utils = AuthenticationUtils(
            served.with_attribute(SecurityRequestAttributes.STATE_BAG, state),
        )
        error = await utils.get_last_authentication_error()
        return {"error": None if error is None else type(error).__name__}

    @application.get("/login")
    async def login_page() -> dict[str, object]:
        """The main firewall's login page."""
        return {"page": "login"}

    @application.post("/json_login")
    async def json_login(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
        """The endpoint the JSON login hands a logged-in request on to."""
        return {"user": user.get_user_identifier()}

    for path in ("/", "/api/me", "/chained/me", "/loaderless/me"):

        async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
            """Answer the user the request is authenticated as."""
            return {"user": user.get_user_identifier()}

        application.add_api_route(path, me, methods=["GET"])

    setup(application, served_by)
    return application


kernel = Kernel(
    "tests.fixtures.scoped_provider_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
app = serve(kernel)
