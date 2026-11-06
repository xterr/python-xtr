"""A deployment whose issuer parameter carries a path.

A parameter written as it stands is known before the bundle loads, so the
configuration refuses it then, as it refuses the same value written in place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import configure, parameters

from xtr_security_oauth2_server.bundle import AuthorizationServerConfig, OAuth2ServerConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["app_parameters", "oauth2_server"]


@parameters
def app_parameters() -> Mapping[str, object]:
    """Name an issuer no discovery document could be found under."""
    return {"app": {"issuer": "https://x.example/path"}}


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Issue tokens under the origin the parameter names."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(issuer="%app.issuer%"),
    )
