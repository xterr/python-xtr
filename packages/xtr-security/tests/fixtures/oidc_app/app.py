"""The served FastAPI application the OIDC integration test drives.

The firewall — a subscriber over the kernel lifecycle's events —
authenticates every request the configured firewall's matcher claims through
the OIDC token handler; the one route returns the current user, so a valid
token answers 200 and a missing or bad one answers 401.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser

from tests.fixtures.oidc_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

app = FastAPI()


@app.get("/api/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    """Return the current user's identifier, read from the token's claims."""
    return {"user": user.get_user_identifier()}


kernel = Kernel(
    "tests.fixtures.oidc_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
