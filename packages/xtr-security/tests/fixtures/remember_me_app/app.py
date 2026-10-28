"""The served FastAPI application the remember-me and switch-user tests drive.

The login form carries the ask to be remembered; the home page answers with
the user the request is authenticated as — the user the cookie remembered,
or the user a switch settled on — so a test that reads the page back
exercises the whole chain: the login that stages the cookie, the response
listener that writes it, the authenticator that spends it, and the switch
step that changes the user under the request's own feet.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_http_kernel.bridge import Response
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser

from tests.fixtures.remember_me_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

app = FastAPI()


@app.get("/login")
async def login_page(response: Injected[Response]) -> Response:
    """Render the login form, carrying the ask to be remembered."""
    _ = await response.get_body().write(
        (
            b'<form method="post" action="/login_check">'
            b'<input name="_username"><input name="_password">'
            b'<input type="checkbox" name="_remember_me" value="1">'
            b"</form>"
        ),
    )
    return response.with_header("content-type", "text/html")


@app.get("/secure")
async def secure_page(response: Injected[Response]) -> Response:
    """The page the channel rule demands HTTPS of."""
    _ = await response.get_body().write(b"<p>secure</p>")
    return response.with_header("content-type", "text/html")


@app.get("/")
async def home(
    response: Injected[Response],
    user: Annotated[UserInterface, CurrentUser()],
) -> Response:
    """The protected page: the user the request is authenticated as."""
    _ = await response.get_body().write(
        f"<p>{user.get_user_identifier()}</p>".encode(),
    )
    return response.with_header("content-type", "text/html")


kernel = Kernel(
    "tests.fixtures.remember_me_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
