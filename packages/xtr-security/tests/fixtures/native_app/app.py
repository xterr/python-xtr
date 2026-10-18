"""The served application whose routes carry the framework's own security params.

The firewall — a subscriber over the kernel lifecycle's events — authenticates
every request the configuration's firewall claims; the routes below then
resolve their parameters the way the framework documents it, with its own
security objects, so a served test proves the two coexist: the firewall runs
first, and the native params read the same request after it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, Security
from fastapi.security import APIKeyHeader, HTTPBearer, SecurityScopes
from fastapi.security.http import HTTPAuthorizationCredentials
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import CurrentUser

from tests.fixtures.native_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

_bearer = HTTPBearer(auto_error=False)
_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


async def _ping() -> str:
    """A plain framework dependency, resolved the way the framework documents it."""
    return "pong"


def _scopes_of(security_scopes: SecurityScopes) -> list[str]:
    """A dependency reading the scopes the route's ``Security`` markers accumulate."""
    return list(security_scopes.scopes)


app = FastAPI()


@app.get("/api/open/bearer")
async def open_bearer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> dict[str, object]:
    """A public route whose bearer credential the framework itself resolves."""
    return {"credential": None if credentials is None else credentials.credentials}


@app.get("/api/scopes")
async def scopes(
    accumulated: Annotated[list[str], Security(_scopes_of, scopes=["books:read"])],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
    user: Annotated[UserInterface, CurrentUser()],
) -> dict[str, object]:
    """A secured route whose accumulated ``SecurityScopes`` the framework resolves."""
    return {
        "scopes": accumulated,
        "credential": None if credentials is None else credentials.credentials,
        "user": user.get_user_identifier(),
    }


@app.get("/api/key")
async def key(
    presented: Annotated[str | None, Security(_key_header)],
    pong: Annotated[str, Depends(_ping)],
) -> dict[str, object]:
    """A secured route reading an API key header through the framework's own object."""
    return {"key": presented, "pong": pong}


kernel = Kernel(
    "tests.fixtures.native_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
