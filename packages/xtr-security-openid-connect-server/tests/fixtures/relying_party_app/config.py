"""The client application's security: one stateful firewall signing in with OpenID Connect.

The login is the repository's own relying party, configured as an application
registered at the fixture provider would configure it: the provider's issuer,
the public client the provider seeds, no secret, a proof key, and the ID
token's signature verified with the algorithm the provider signs with. The
user is read from the provider's userinfo endpoint, so a sign-in crosses every
endpoint the provider serves.

The account page needs a signed-in user, so a visit to it starts the login,
through the firewall's entry point; the callback, where the provider sends the
browser back, is the login's own, and returns the browser to the page it asked
for.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

from xtr_dependency_injection import configure
from xtr_security.bundle import (
    AccessControlConfig,
    FirewallConfig,
    InMemoryUserProviderConfig,
    OidcLoginConfig,
    SecurityConfig,
)

from tests.fixtures.openid_app.config import ALGORITHM, USER_IDENTIFIER
from tests.support.served import CLIENT_ID, REDIRECT_URI
from tests.support.signing import ISSUER

__all__ = ["ACCOUNT_PATH", "CALLBACK_PATH", "FIREWALL", "security"]

#: The firewall the login runs on, which names its services.
FIREWALL: Final = "main"

#: Where the provider sends the browser back: the redirect URI the provider
#: has registered for the client, served by this application.
CALLBACK_PATH: Final = urlsplit(REDIRECT_URI).path

#: The page only a signed-in user reaches. Not the root, where the login lands
#: when no page asked for it, so a return here is the return to the page asked for.
ACCOUNT_PATH: Final = "/account"


@configure
def security() -> SecurityConfig:
    """Sign the user in with the fixture provider, keeping the login in a session."""
    return SecurityConfig(
        providers={
            "users": InMemoryUserProviderConfig(users={USER_IDENTIFIER: {"roles": ["ROLE_USER"]}}),
        },
        firewalls={
            FIREWALL: FirewallConfig(
                pattern=r"^/",
                stateless=False,
                provider="users",
                authenticators=(
                    OidcLoginConfig(
                        issuer=ISSUER,
                        client_id=CLIENT_ID,
                        token_endpoint_auth_method="none",
                        check_path=CALLBACK_PATH,
                        signature_verifier_algorithms=(ALGORITHM,),
                    ),
                ),
            ),
        },
        access_control=(AccessControlConfig(path=r"^/account", attribute="IS_AUTHENTICATED"),),
    )
