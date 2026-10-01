"""The served FastAPI application the JWT integration tests drive."""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Injected, Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall, IsGranted

from tests.fixtures.jwt_app.bundles import BUNDLES
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface

__all__ = ["app", "kernel"]

app = FastAPI(dependencies=[Firewall()])


@app.get("/api/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, object]:
    """Return the current user's identifier and roles."""
    return {"user": user.get_user_identifier(), "roles": list(user.get_roles())}


@app.get("/api/admin/panel", dependencies=[IsGranted("ROLE_ADMIN")])
async def admin_panel() -> dict[str, str]:
    """An admin-only route, guarded by an IsGranted dependency."""
    return {"status": "admin"}


@app.get("/manager")
async def manager(tokens: Injected[JwtTokenManagerInterface]) -> dict[str, str]:
    """Prove the token manager is registered and injectable."""
    return {"manager": type(tokens).__name__}


kernel = Kernel(
    "tests.fixtures.jwt_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
