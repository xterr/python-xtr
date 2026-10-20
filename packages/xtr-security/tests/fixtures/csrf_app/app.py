"""The served FastAPI application the CSRF tests drive.

The login page mints the tokens its forms carry — through the very manager
the bundle wires, over the session the request reattached — so a test that
submits one exercises the whole chain: the badge the form login builds, the
passport check that settles it, the manager that vouches for it.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_http_kernel.bridge import Response
from xtr_http_message_contracts import ServerRequestInterface
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface
from xtr_security_http import AuthenticationUtils, CurrentUser
from xtr_security_http._parked_session import parked_session_of

from tests.fixtures.csrf_app.bundles import BUNDLES
from xtr_security.bundle._csrf_wiring import ParkedRequest

__all__ = ["app", "kernel"]

app = FastAPI()


@app.get("/login")
async def login_page(
    response: Injected[Response],
    request_park: Injected[ParkedRequest],
    csrf_token_manager: Injected[CsrfTokenManagerInterface],
) -> Response:
    """Render the login form, minting the tokens its forms carry.

    The last error is read off the chain's request — the one carrying the
    state bag the failure stored the error under — which the park holds for
    exactly the services a request builds. The session is saved and its
    cookie staged here because the response-time save listener has not
    landed yet: the library leaves the save to the caller, and this page
    is the caller its tokens must survive.
    """
    request = cast("ServerRequestInterface", request_park.request)
    token = await csrf_token_manager.get_token("authenticate")
    logout_token = await csrf_token_manager.get_token("logout")
    error = await AuthenticationUtils(request).get_last_authentication_error()
    message = "" if error is None else error.get_message_key()
    session = parked_session_of(request)
    if session is not None:
        await session.save()
        staged_cookie = session.staged_set_cookie()
        if staged_cookie is not None:
            response = response.with_header("set-cookie", staged_cookie)
    _ = await response.get_body().write(
        (
            f"<p>{message}</p>"
            '<form method="post" action="/login_check">'
            '<input name="_username"><input name="_password">'
            f'<input type="hidden" name="_csrf_token" value="{token.get_value()}">'
            f'<input type="hidden" name="_logout_token" value="{logout_token.get_value()}">'
            "</form>"
        ).encode(),
    )
    return response.with_header("content-type", "text/html")


@app.get("/")
async def home(
    response: Injected[Response],
    user: Annotated[UserInterface, CurrentUser()],
) -> Response:
    """The protected page: the current user."""
    _ = await response.get_body().write(
        f"<p>{user.get_user_identifier()}</p>".encode(),
    )
    return response.with_header("content-type", "text/html")


kernel = Kernel(
    "tests.fixtures.csrf_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
