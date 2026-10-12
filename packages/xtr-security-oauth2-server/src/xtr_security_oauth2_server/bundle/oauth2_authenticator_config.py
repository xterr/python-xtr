"""Naming the bearer-token authenticator on a firewall."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["OAuth2AuthenticatorConfig"]


@dataclass(frozen=True, slots=True)
class OAuth2AuthenticatorConfig:
    """Put this deployment's access tokens in front of a firewall's routes.

    It carries nothing. Everything the authenticator needs is already a
    decision of the server rather than of one firewall — which keys read a
    token, which issuer it must claim, what prefix its scopes become roles
    under — so there is nothing left for a firewall to say but *that* it
    accepts these tokens:

    ```python
    FirewallConfig(pattern=r"^/api", authenticators=(OAuth2AuthenticatorConfig(),))
    ```

    One authenticator is built per firewall even so, because it is handed that
    firewall's own user provider: the same token names a different user on an
    API reading its staff from one store and its customers from another.
    """
