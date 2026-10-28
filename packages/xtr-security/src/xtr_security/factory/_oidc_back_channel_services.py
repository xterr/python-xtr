"""The back-channel logout services an OIDC login wires behind its firewall.

The provider ends one of its sessions out of band: the logout token it
pushes is verified and recorded, the handler answering the push is the
application's route to map, and the listener refusing the ended session's
token runs wherever the refreshed-user check is announced. The provider's
own session ends through the end-session listener, which redirects the
application's logout to the provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_cache import (
    CacheItemPoolInterface,
)
from xtr_clock import ClockInterface
from xtr_dependency_injection import Target
from xtr_event_dispatcher.bundle import LISTENER_TAG, SUBSCRIBER_TAG
from xtr_security_http import HttpUtils

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.exception import InvalidConfigurationError
from xtr_security.oidc_back_channel_logout_handler import OidcBackChannelLogoutHandler

if TYPE_CHECKING:
    from xtr_dependency_injection import ServiceConfigurator, ServiceKey
    from xtr_security_http.oidc import (
        OidcDiscovery,
        OidcSignatureVerifier,
    )

    from xtr_security.bundle.oidc_configs import OidcLoginConfig

__all__ = ["register_back_channel_logout", "register_end_session_listener"]


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression;
    the container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker


def register_back_channel_logout(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    discovery_key: ServiceKey,
    verifier_key: ServiceKey | None,
) -> None:
    """Register the ended sessions, the pushed-token handler and its listener.

    The pool the ended sessions are remembered in is the application's own
    — a shared backend every server of the application reaches, registered
    as a ``CacheItemPoolInterface`` service — never one the bundle builds
    silently: a pool local to one process loses what another one recorded.

    Raises:
        InvalidConfigurationError: When the login configures no signature
            verifier — the pushed token's signature is the one check that
            makes it the provider's, and it can never be skipped.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's event import
        CheckRefreshedUserEvent,
    )
    from xtr_security_http.event_listener import (  # noqa: PLC0415 -- the family's listener import
        OidcBackChannelLogoutListener,
    )
    from xtr_security_http.oidc import (  # noqa: PLC0415 -- guarded behind the oidc extra
        OidcBackChannelLogout,
        OidcEndedSessions,
        OidcLogoutToken,
    )

    backchannel = settings.backchannel_logout
    if backchannel is None or not backchannel.enable:
        return
    if verifier_key is None:
        raise InvalidConfigurationError(
            f'The back-channel logout of the firewall "{firewall_name}" needs its '
            "logout tokens' signatures verified; set signature_verifier_algorithms "
            "on the login.",
        )

    def oidc_ended_sessions(pool: CacheItemPoolInterface) -> OidcEndedSessions:
        """Build the ended sessions over the application's shared pool."""
        return OidcEndedSessions(pool, firewall_name, backchannel.lifetime)

    oidc_ended_sessions.__annotations__ = {
        "pool": CacheItemPoolInterface,
        "return": OidcEndedSessions,
    }
    oidc_ended_sessions.__name__ = f"oidc_ended_sessions_{firewall_name}"
    oidc_ended_sessions.__qualname__ = oidc_ended_sessions.__name__
    ended_sessions_key = services.set(
        oidc_ended_sessions, qualifier=f"{firewall_name}#oidc_ended_sessions"
    ).key

    def oidc_logout_token(clock: ClockInterface | None = None) -> OidcLogoutToken:
        """Build the reader of a verified logout token's claims."""
        return OidcLogoutToken(clock=clock)

    oidc_logout_token.__annotations__ = {
        "clock": ClockInterface | None,
        "return": OidcLogoutToken,
    }
    oidc_logout_token.__name__ = f"oidc_logout_token_{firewall_name}"
    oidc_logout_token.__qualname__ = oidc_logout_token.__name__
    logout_token_key = services.set(
        oidc_logout_token, qualifier=f"{firewall_name}#oidc_logout_token"
    ).key

    def oidc_back_channel_logout(
        verifier: object,
        logout_token: object,
        discovery: object,
        ended_sessions: object,
    ) -> OidcBackChannelLogout:
        """Build what verifies a pushed logout token and records its session end."""
        return OidcBackChannelLogout(
            cast("OidcSignatureVerifier", verifier),
            cast("OidcLogoutToken", logout_token),
            cast("OidcDiscovery", discovery),
            settings.client_id,
            cast("OidcEndedSessions", ended_sessions),
        )

    oidc_back_channel_logout.__annotations__ = {
        "verifier": _qualified(verifier_key),
        "logout_token": _qualified(logout_token_key),
        "discovery": _qualified(discovery_key),
        "ended_sessions": _qualified(ended_sessions_key),
        "return": OidcBackChannelLogout,
    }
    oidc_back_channel_logout.__name__ = f"oidc_back_channel_logout_{firewall_name}"
    oidc_back_channel_logout.__qualname__ = oidc_back_channel_logout.__name__
    logout_key = services.set(
        oidc_back_channel_logout, qualifier=f"{firewall_name}#oidc_back_channel_logout"
    ).key

    def oidc_back_channel_logout_handler(logout: object) -> OidcBackChannelLogoutHandler:
        """Build the handler the application's back-channel route answers through."""
        return OidcBackChannelLogoutHandler(cast("OidcBackChannelLogout", logout))

    oidc_back_channel_logout_handler.__annotations__ = {
        "logout": _qualified(logout_key),
        "return": OidcBackChannelLogoutHandler,
    }
    oidc_back_channel_logout_handler.__name__ = f"oidc_back_channel_logout_handler_{firewall_name}"
    oidc_back_channel_logout_handler.__qualname__ = oidc_back_channel_logout_handler.__name__
    _ = services.set(oidc_back_channel_logout_handler, qualifier=firewall_name)

    def oidc_back_channel_logout_listener(
        ended_sessions: object,
    ) -> OidcBackChannelLogoutListener:
        """Build the callable refusing a token whose provider session ended."""
        return OidcBackChannelLogoutListener(
            cast("OidcEndedSessions", ended_sessions), firewall_name
        )

    oidc_back_channel_logout_listener.__annotations__ = {
        "ended_sessions": _qualified(ended_sessions_key),
        "return": OidcBackChannelLogoutListener,
    }
    oidc_back_channel_logout_listener.__name__ = (
        f"oidc_back_channel_logout_listener_{firewall_name}"
    )
    oidc_back_channel_logout_listener.__qualname__ = oidc_back_channel_logout_listener.__name__
    # A plain callable on the refreshed-user check, on the dispatcher the
    # context listener announces it on — added as a listener, not a
    # subscriber, exactly the shape the check's announcer expects.
    _ = services.set(
        oidc_back_channel_logout_listener,
        qualifier=f"{firewall_name}#oidc_back_channel_logout_listener",
    ).add_tag(LISTENER_TAG, event=CheckRefreshedUserEvent)


def register_end_session_listener(
    services: ServiceConfigurator,
    firewall_name: str,
    settings: OidcLoginConfig,
    discovery_key: ServiceKey,
) -> None:
    """Register the listener redirecting the application's logout to the provider.

    The listener runs on the firewall's own dispatcher, ahead of the default
    logout listener that answers a logout nothing else answered: its
    ``65`` priority is its own subscription's, and a login carrying no ID
    token — or a provider announcing no end-session endpoint — leaves the
    logout a local one.
    """
    from xtr_security_http.event_listener import (  # noqa: PLC0415 -- the family's listener import
        OidcEndSessionListener,
    )

    end_session = settings.end_session
    if end_session is None or not end_session.enable:
        return

    def oidc_end_session_listener(
        discovery: object,
        http_utils: HttpUtils,
    ) -> OidcEndSessionListener:
        """Build the listener reading the provider's end-session endpoint."""
        return OidcEndSessionListener(
            cast("OidcDiscovery", discovery),
            http_utils,
            end_session.post_logout_redirect_path,
        )

    oidc_end_session_listener.__annotations__ = {
        "discovery": _qualified(discovery_key),
        "http_utils": HttpUtils,
        "return": OidcEndSessionListener,
    }
    oidc_end_session_listener.__name__ = f"oidc_end_session_listener_{firewall_name}"
    oidc_end_session_listener.__qualname__ = oidc_end_session_listener.__name__
    dispatcher = firewall_dispatcher_name(firewall_name)
    _ = services.set(
        oidc_end_session_listener,
        qualifier=f"{firewall_name}#oidc_end_session_listener",
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)
