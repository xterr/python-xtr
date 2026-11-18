"""The paths both placeholder fixtures configure, and the variables they are read from."""

from __future__ import annotations

from typing import Final

__all__ = ["ALICE_PASSWORD", "CHECK_PATH", "ENVIRON", "LOGIN_PATH", "LOGOUT_PATH", "LOGOUT_TARGET"]

LOGIN_PATH: Final = "/sign-in"
"""Where the form lives."""

CHECK_PATH: Final = "/sign-in/check"
"""Where the form is submitted."""

LOGOUT_PATH: Final = "/sign-out"
"""Where a logout is asked for."""

LOGOUT_TARGET: Final = "https://web.test/"
"""Where a logout sends the browser: the single-page application's own origin."""

ALICE_PASSWORD: Final = "secret"
"""The password of the one user, kept out of the configuration as a deployment keeps it."""

ENVIRON: Final = {
    "LOGIN_PATH": LOGIN_PATH,
    "CHECK_PATH": CHECK_PATH,
    "LOGOUT_PATH": LOGOUT_PATH,
    "WEB_APP_ORIGIN": LOGOUT_TARGET,
    "ALICE_PASSWORD": ALICE_PASSWORD,
}
"""The environment a deployment sets them in."""
