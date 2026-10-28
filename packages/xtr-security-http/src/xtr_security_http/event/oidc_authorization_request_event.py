"""The event dispatched before the caller is sent to the OIDC authorization endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["OidcAuthorizationRequestEvent"]


@final
class OidcAuthorizationRequestEvent(Event):
    """Announces the authorization request an OIDC login is about to send.

    Dispatched while the login's entry point builds the redirect to the
    provider, before anything is stored in the session. A listener reads the
    request the login started from and the extra parameters the wiring
    configured, and may compute the parameters per request — a ``ui_locales``
    following the request's locale, a ``login_hint`` read from the session.

    The parameters the authenticator computes itself are not the listener's to
    set: the authenticator refuses one that does, so that no configuration can
    weaken the ``state``, the ``nonce`` or the PKCE challenge the flow's
    security rests on.

    Not a frozen dataclass: the whole point is that a listener replaces the
    parameters.
    """

    __slots__ = ("_firewall_name", "_params", "_request")

    def __init__(
        self,
        request: ServerRequestInterface,
        firewall_name: str,
        params: Mapping[str, str],
    ) -> None:
        """Record the request the login started from, the firewall, and the extra parameters.

        Args:
            request: The request that reached the entry point.
            firewall_name: The firewall the login runs under.
            params: The extra parameters of the authorization request,
                starting from the configured ones.
        """
        self._request = request
        self._firewall_name = firewall_name
        self._params: dict[str, str] = dict(params)

    def get_request(self) -> ServerRequestInterface:
        """Return the request the login started from."""
        return self._request

    def get_firewall_name(self) -> str:
        """Return the firewall the login runs under."""
        return self._firewall_name

    def get_params(self) -> dict[str, str]:
        """Return the extra parameters of the authorization request.

        The mapping is a copy taken now, so a later :meth:`set_param` does
        not change a mapping already returned.
        """
        return dict(self._params)

    def set_params(self, params: Mapping[str, str]) -> None:
        """Replace the whole list of extra parameters with ``params``.

        Prefer :meth:`set_param` and :meth:`remove_param` to touch one
        parameter, so that several listeners can each set their own without
        overwriting what the others did.
        """
        self._params = dict(params)

    def set_param(self, name: str, value: str) -> None:
        """Set the extra parameter ``name`` to ``value``."""
        self._params[name] = value

    def remove_param(self, name: str) -> None:
        """Drop the extra parameter ``name``, when it is set."""
        _ = self._params.pop(name, None)
