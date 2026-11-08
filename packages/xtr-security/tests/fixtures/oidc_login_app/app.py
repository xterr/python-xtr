"""The served application the OIDC login tests drive.

The one route is an account page, which only a signed-in user reaches: an
anonymous visit is answered by the firewall's entry point, the redirect to the
provider, before the route is.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser

from xtr_security.bundle import SecurityBundle

__all__ = ["app", "kernel"]

app = FastAPI()


@app.get("/account/profile")
async def profile(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    """Return who is signed in."""
    return {"user": user.get_user_identifier()}


kernel = Kernel(
    "tests.fixtures.oidc_login_app",
    env="test",
    bundles={SecurityBundle: {"all": True}},
    concurrent_scoped_access=True,
)
setup(app, kernel)
