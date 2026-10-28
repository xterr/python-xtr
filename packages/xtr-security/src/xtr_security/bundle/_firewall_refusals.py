"""The refusals a firewall's own configuration is checked against at build.

Each refusal names the piece of stateful machinery the configuration asks
for and the firewall it was asked of: a stateless firewall has no session,
so everything that keeps its promise in one — a login's stored errors, a
logout's proven tokens, a back-channel logout's recorded sessions, the
route markers' manager — would silently go nowhere, reading as protection
while refusing nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security.bundle.authenticator_configs import FormLoginConfig
from xtr_security.bundle.oidc_configs import OidcLoginConfig
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from xtr_security.firewall_config import FirewallConfig

__all__ = [
    "refuse_a_back_channel_logout_on_a_stateless_firewall",
    "refuse_a_form_login_on_a_stateless_firewall",
    "refuse_csrf_route_markers_on_a_stateless_firewall",
]


def refuse_a_back_channel_logout_on_a_stateless_firewall(
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Refuse a back-channel logout a stateless firewall could never act on.

    The ended sessions a back-channel logout records are acted on by the
    refreshed-user check, which only a stateful firewall's context listener
    announces: on a stateless firewall the recording would be machinery
    nothing reads, reading as protection while refusing nothing.

    Raises:
        InvalidConfigurationError: When a stateless firewall's OIDC login
            asks for a back-channel logout.
    """
    for authenticator in firewall.authenticators:
        if (
            isinstance(authenticator, OidcLoginConfig)
            and authenticator.backchannel_logout is not None
            and authenticator.backchannel_logout.enable
            and firewall.stateless
        ):
            raise InvalidConfigurationError(
                f'The OIDC login of the firewall "{name}" asks for a back-channel '
                "logout, which needs a stateful firewall; set stateless=False.",
            )


def refuse_a_form_login_on_a_stateless_firewall(
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Refuse a form login on a firewall that keeps no session.

    The login's errors are stored on the session and its success rotates it;
    on a stateless firewall both would silently go nowhere, reading as a
    login while logging nothing in.

    Raises:
        InvalidConfigurationError: When a stateless firewall configures a
            form login.
    """
    if firewall.stateless and any(
        isinstance(authenticator, FormLoginConfig) for authenticator in firewall.authenticators
    ):
        raise InvalidConfigurationError(
            f'The form login of the firewall "{name}" needs the session its errors '
            "are stored in and its success rotates; set stateless=False.",
        )


def refuse_csrf_route_markers_on_a_stateless_firewall(
    name: str,
    firewall: FirewallConfig,
) -> None:
    """Refuse route-marker tokens on a firewall that keeps no session.

    The manager the markers resolve through keeps its tokens in the session
    the request reattached; on a stateless firewall there is none, so the
    markers would refuse every request they guard — protection that reads
    as a refusal while proving nothing.

    Raises:
        InvalidConfigurationError: When a stateless firewall declares
            ``csrf_route_markers``.
    """
    if firewall.stateless and firewall.csrf_route_markers:
        raise InvalidConfigurationError(
            f'The cross-site request forgery markers of the firewall "{name}" need '
            "the session their tokens are stored in; set stateless=False.",
        )
