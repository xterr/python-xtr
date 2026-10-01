"""The served FastAPI application the integration tests drive.

An app-level firewall dependency authenticates every request its matchers claim;
routes then use the firewall's scopes, ``IsGranted`` in every shape, and
``CurrentUser`` so the served tests exercise the whole request surface.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser, Firewall, IsGranted

from tests.fixtures.security_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

_api = Firewall("api")


def _owns_book(context: object, subject: object) -> bool:
    """A closure attribute: grant when the subject book is the sample one."""
    del context
    return subject == "owned"


app = FastAPI(dependencies=[Firewall()])


@app.get("/open/ping")
async def open_ping() -> dict[str, str]:
    """An open firewall's route: no authentication."""
    return {"status": "open"}


@app.get("/api/public/ping")
async def public_ping() -> dict[str, str]:
    """A PUBLIC_ACCESS route inside the secured firewall."""
    return {"status": "public"}


@app.get("/api/me")
async def me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
    """Return the current user's identifier."""
    return {"user": user.get_user_identifier()}


@app.get("/api/books", dependencies=[_api.scoped("books:read")])
async def books() -> list[dict[str, str]]:
    """A scoped route: needs the ``books:read`` scope."""
    return [{"isbn": "0262510871"}]


@app.get("/api/reports", dependencies=[_api.scoped("reports:write")])
async def reports() -> dict[str, str]:
    """A scoped route: needs the ``reports:write`` scope."""
    return {"status": "reported"}


@app.delete("/api/books/{isbn}")
@IsGranted("ROLE_ADMIN")
async def delete_book(isbn: str) -> dict[str, str]:
    """An admin-only route, guarded by the IsGranted decorator."""
    return {"deleted": isbn}


@app.get("/api/admin/panel", dependencies=[IsGranted("ROLE_ADMIN")])
async def admin_panel() -> dict[str, str]:
    """An admin route, guarded by an IsGranted dependency."""
    return {"status": "admin"}


@app.put("/api/books/{isbn}")
@IsGranted(_owns_book, subject="isbn")
async def edit_book(isbn: str) -> dict[str, str]:
    """A route guarded by a callable attribute over a path-parameter subject."""
    return {"isbn": isbn}


kernel = Kernel(
    "tests.fixtures.security_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
