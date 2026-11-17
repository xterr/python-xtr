"""The form-login fixture's pages and security, with the login-holding listener added."""

from __future__ import annotations

from xtr_dependency_injection import Kernel

from tests.fixtures.form_login_app.app import serve
from tests.fixtures.form_login_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

kernel = Kernel(
    "tests.fixtures.firewall_race_app",
    env="test",
    bundles=BUNDLES,
    resources=(
        "tests.fixtures.form_login_app.config",
        "tests.fixtures.form_login_app.services",
        "tests.fixtures.firewall_race_app.listeners",
    ),
    concurrent_scoped_access=True,
)
app = serve(kernel)
