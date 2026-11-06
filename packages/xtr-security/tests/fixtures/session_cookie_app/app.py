"""The served application the session cookie tests drive."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_http_kernel.bridge import Response
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser

from xtr_security.bundle import SecurityBundle

__all__ = ["app", "kernel"]

app = FastAPI()


@app.get("/login")
async def login_page(response: Injected[Response]) -> Response:
    """The page an anonymous request is sent to."""
    _ = await response.get_body().write(b"<form></form>")
    return response.with_header("content-type", "text/html")


@app.get("/")
async def home(
    response: Injected[Response],
    user: Annotated[UserInterface, CurrentUser()],
) -> Response:
    """The protected page: the current user."""
    _ = await response.get_body().write(f"<p>{user.get_user_identifier()}</p>".encode())
    return response.with_header("content-type", "text/html")


kernel = Kernel(
    "tests.fixtures.session_cookie_app",
    env="test",
    bundles={SecurityBundle: {"all": True}},
    concurrent_scoped_access=True,
)
setup(app, kernel)
