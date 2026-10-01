"""The served application the seam test drives, secured by the fake authenticator."""

from __future__ import annotations

from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup
from xtr_security_http import Firewall

from tests.fixtures.seam_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

_api = Firewall("api")

app = FastAPI(dependencies=[Firewall()])


@app.get("/api/ping")
async def ping() -> dict[str, str]:
    """A route the fake firewall guards."""
    return {"status": "ok"}


@app.get("/api/scoped", dependencies=[_api.scoped("fake:read")])
async def scoped() -> dict[str, str]:
    """A route the fake handler's scope gates."""
    return {"status": "scoped"}


kernel = Kernel(
    "tests.fixtures.seam_app",
    env="test",
    bundles=BUNDLES,
    concurrent_scoped_access=True,
)
setup(app, kernel)
