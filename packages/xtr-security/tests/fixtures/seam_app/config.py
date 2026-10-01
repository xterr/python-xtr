"""The security configuration the seam fixture is built from.

A firewall whose authenticator is the fake ``fake_oauth2`` one — an instance of a
config type the family never declared — with an access-control rule that gates a
route by a scope the fake handler grants.
"""

from __future__ import annotations

from xtr_dependency_injection import configure

from tests.fixtures.seam_app.factories import FakeOAuth2Config
from xtr_security.bundle import AccessControlConfig, FirewallConfig, SecurityConfig

__all__ = ["security"]


@configure
def security() -> SecurityConfig:
    """Return the seam fixture's security configuration."""
    return SecurityConfig(
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/api",
                authenticators=(FakeOAuth2Config(realm="fake"),),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/api", attribute="IS_AUTHENTICATED"),),
    )
