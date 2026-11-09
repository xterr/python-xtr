"""The form-login fixture's pages, served over a session kept in this process's memory.

The pages, the security configuration and the bundles are the form-login
fixture's own; only the session storage is this fixture's, so a test driving
both applications reads whether the two storages answer alike.
"""

from __future__ import annotations

from xtr_dependency_injection import Kernel

from tests.fixtures.form_login_app.app import serve
from tests.fixtures.form_login_app.bundles import BUNDLES

__all__ = ["app", "kernel"]

kernel = Kernel(
    "tests.fixtures.form_login_memory_app",
    env="test",
    bundles=BUNDLES,
    resources=(
        "tests.fixtures.form_login_app.config",
        "tests.fixtures.form_login_memory_app.services",
    ),
    concurrent_scoped_access=True,
)
app = serve(kernel)
