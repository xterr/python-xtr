"""The paths both placeholder fixtures configure, and the variables they are read from."""

from __future__ import annotations

from typing import Final

__all__ = ["CHECK_PATH", "ENVIRON", "LOGIN_PATH", "LOGOUT_PATH", "LOGOUT_TARGET"]

LOGIN_PATH: Final = "/sign-in"
"""Where the form lives."""

CHECK_PATH: Final = "/sign-in/check"
"""Where the form is submitted."""

LOGOUT_PATH: Final = "/sign-out"
"""Where a logout is asked for."""

LOGOUT_TARGET: Final = "https://web.test/"
"""Where a logout sends the browser: the single-page application's own origin."""

ENVIRON: Final = {
    "LOGIN_PATH": LOGIN_PATH,
    "CHECK_PATH": CHECK_PATH,
    "LOGOUT_PATH": LOGOUT_PATH,
    "WEB_APP_ORIGIN": LOGOUT_TARGET,
}
"""The environment a deployment sets them in."""
