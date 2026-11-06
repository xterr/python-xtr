"""The bundle turning the OAuth 2.0 authorization server into an OpenID Connect provider."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import Bundle, as_bundle, required_bundle

from .openid_connect_server_config import OpenIdConnectServerConfig

__all__ = ["OpenIdConnectServerBundle"]


@final
@required_bundle("xtr_security_oauth2_server.bundle:OAuth2ServerBundle")
@required_bundle("xtr_security.bundle:SecurityBundle")
@required_bundle("xtr_clock.bundle:ClockBundle")
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle")
@required_bundle("xtr_http_kernel.bundle:HttpKernelBundle")
@as_bundle("openid_connect_server", config=OpenIdConnectServerConfig)
class OpenIdConnectServerBundle(Bundle[OpenIdConnectServerConfig]):
    """Turns this deployment's authorization server into an OpenID Connect provider.

    An identity layer exists only on top of a server that already issues
    access tokens, so listing this bundle brings the authorization server
    along, with the security family, the clock, the event dispatcher and the
    HTTP kernel that server is built on. The authorization server knows
    nothing of this bundle: this one plugs into it.

    Each peer is named by its ``"module:Class"`` string, the way the
    authorization server names its own: the kernel imports each one as it
    resolves the bundles, so a peer that is not installed is reported there,
    by name.

    It builds and boots with no configuration at all.
    """

    __slots__ = ()
