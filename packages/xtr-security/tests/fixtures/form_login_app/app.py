"""The served FastAPI application the form-login tests drive.

The login page answers what the last login attempt left — the error it failed
with and the username it carried — read the way a login page reads them, off
the state the chain parked on the request; every other page answers the user
the request is authenticated as, and the form page the form it was posted too.
So a test that posts a form or a JSON document and reads a page back exercises
the whole chain over the body as it was posted: the form login, the JSON
login, the switch posted in a form, and the session that carries each of them
to the next request.

The pages are built by :func:`serve` over the kernel they are set up on, so
the fixture keeping its sessions in this process's memory serves the very same
pages over a storage of its own.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import FastAPI, Request
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_http_message_contracts import ServerRequestInterface
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import AuthenticationUtils, CurrentUser, SecurityRequestAttributes

from tests.fixtures.form_login_app.bundles import BUNDLES

__all__ = ["app", "kernel", "serve"]


def serve(served_by: Kernel) -> FastAPI:
    """Return the fixture's pages as an application set up on ``served_by``."""
    application = FastAPI()

    @application.get("/login")
    async def login_page(
        request: Request,
        served: Injected[ServerRequestInterface],
    ) -> dict[str, object]:
        """Answer what the last login attempt left: the error and the username it carried.

        The chain parks the session it reattached on the request's state bag —
        the one the kernel keeps on the connection's scope — so the page reads
        the attempt through the served message carrying that bag, the way the
        chain's own steps are handed it.
        """
        state = cast("dict[str, object]", request.scope["state"])
        utils = AuthenticationUtils(
            served.with_attribute(SecurityRequestAttributes.STATE_BAG, state),
        )
        error = await utils.get_last_authentication_error()
        return {
            "error": None if error is None else type(error).__name__,
            "key": None if error is None else error.get_message_key(),
            "username": await utils.get_last_username(),
        }

    @application.get("/")
    async def home(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
        """The protected page: the user the request is authenticated as."""
        return {"user": user.get_user_identifier()}

    @application.post("/echo")
    async def echo(
        request: Request,
        user: Annotated[UserInterface, CurrentUser()],
    ) -> dict[str, object]:
        """The protected form page: the user the request is authenticated as, and its form."""
        form = await request.form()
        return {
            "user": user.get_user_identifier(),
            "form": {name: str(value) for name, value in form.items()},
        }

    @application.post("/api/login")
    async def api_login(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
        """The endpoint a JSON login with no success handler of its own hands the request on to."""
        return {"user": user.get_user_identifier()}

    @application.get("/api/me")
    async def api_me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
        """The API's protected resource: the user the request is authenticated as."""
        return {"user": user.get_user_identifier()}

    setup(application, served_by)
    return application


kernel = Kernel(
    "tests.fixtures.form_login_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
app = serve(kernel)
