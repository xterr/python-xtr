"""The security family: users, hashers, the role hierarchy, and the one firewall over the routes.

The users are declared inline (``InMemoryUserProviderConfig``) — three accounts whose passwords
are stored as the argon2id hashes ``security:hash-password`` prints, so the ``/token`` route's
``UserPasswordHasher`` verifies them. ``password_hashers`` maps the in-memory user class to the
secure default, so the stored hashes and a fresh one agree. ``role_hierarchy`` makes
``ROLE_ADMIN`` reach ``ROLE_USER``, so an admin need not list both.

One ``api`` firewall covers every route and accepts a self-issued token
(``JwtAuthenticatorConfig`` — the JWT bundle wires it, reading its keys from ``config/jwt.py``).
It loads the user named by the token's ``sub`` claim through the ``users`` provider, so a token
carries identity and the store carries roles. A user is named by its email, so the owner of an
order — the ``email`` it was placed under — is the user the ``ORDER_VIEW`` voter grants it to.

``access_control`` is tried in order: the admin slice needs ``ROLE_ADMIN``, a single order
(``/orders/{number}``) and ``/me`` need a signed-in caller, and everything else — the catalog,
search, the order list and placing an order, health, the token endpoint and the docs — stays
open, the way the shop has always served it.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    AutoHasherConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    SecurityConfig,
)
from xtr_security_core import InMemoryUser
from xtr_security_jwt.bundle import JwtAuthenticatorConfig

__all__ = ["security"]

# A PHC hash string is one indivisible token, so it cannot be wrapped under the line length.
_ADA_HASH = "$argon2id$v=19$m=65536,t=3,p=4$84Osb6GwrtwqCCOPLv7PMA$UGqYyf69GjxPgMuLp7//CRssG9JCiNWOKgpTyB3yOeg"  # noqa: E501
_LIN_HASH = "$argon2id$v=19$m=65536,t=3,p=4$N/oM9ZpvzINxhDdN71LdZw$8ncZYixbZXbQKfvRnYJG3kYoZVBSCVJg8KmnG4HKiKE"  # noqa: E501
_ROOT_HASH = "$argon2id$v=19$m=65536,t=3,p=4$D3kWuxxpnB617MT3c0ENtw$yvaPVytfC91xY6jjwbBp8wFkZUICd8lkvvAJpw2rNRI"  # noqa: E501


@configure
def security() -> SecurityConfig:
    """Three inline users, an admin role above the user role, and the ``api`` firewall."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(
                users={
                    "ada@example.com": {"password": _ADA_HASH, "roles": ("ROLE_USER",)},
                    "lin@example.com": {"password": _LIN_HASH, "roles": ("ROLE_USER",)},
                    "root@example.com": {"password": _ROOT_HASH, "roles": ("ROLE_ADMIN",)},
                },
            ),
        },
        password_hashers={InMemoryUser: AutoHasherConfig()},
        role_hierarchy={"ROLE_ADMIN": ("ROLE_USER",)},
        firewalls={
            "api": FirewallConfig(
                pattern=r"^/",
                provider="users",
                authenticators=(JwtAuthenticatorConfig(),),
            ),
        },
        access_control=(
            AccessControlConfig(path=r"^/admin", attribute="ROLE_ADMIN"),
            AccessControlConfig(path=r"^/orders/.+", attribute="IS_AUTHENTICATED"),
            AccessControlConfig(path=r"^/me", attribute="IS_AUTHENTICATED"),
            AccessControlConfig(path=r"^/", attribute="PUBLIC_ACCESS"),
        ),
    )
