"""The session surface is reachable from the folder that groups it and from the package."""

from __future__ import annotations

import xtr_http_foundation
from xtr_http_foundation import session

_SESSION = ("Session", "SessionCookieConfig", "SessionInterface")


def test_the_folder_exports_the_session_surface() -> None:
    assert sorted(session.__all__) == sorted(_SESSION)


def test_the_package_exports_the_same_session_surface() -> None:
    for name in _SESSION:
        assert getattr(xtr_http_foundation, name) is getattr(session, name)
