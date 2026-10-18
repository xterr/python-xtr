"""A manager listener that records what the firewall's authenticators did, for the tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .traceable_authenticator import TraceableAuthenticator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.firewall.authenticator_manager_listener import (
        AuthenticatorManagerListener,
    )

__all__ = ["TraceableAuthenticatorManagerListener"]


@final
class TraceableAuthenticatorManagerListener(AbstractListener):
    """Wraps a manager listener and records each authenticator the pass chose.

    The wiring swaps a firewall's manager listener for one of these when the
    tooling needs to explain an authentication: which authenticators the
    supports pass chose and skipped, and what each of them answered. The
    wrapper changes nothing about the flow — every call is passed through as
    it came — it only listens: the supporters the pass parked on the
    request's state are re-parked as
    :class:`~xtr_security_http.authenticator.debug.traceable_authenticator.TraceableAuthenticator`
    wrappers, so the pass that authenticates records what each authenticator
    does while it runs it.

    The wrapped listener is stored as given, never unwrapped here:
    :meth:`get_authenticator_manager_listener` is the only door.
    """

    __slots__ = ("_authenticators", "_listener")

    def __init__(self, listener: AuthenticatorManagerListener) -> None:
        """Wrap ``listener`` with nothing recorded yet."""
        self._listener = listener
        self._authenticators: list[TraceableAuthenticator] = []

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Record the authenticators the wrapped supports pass chose and skipped.

        The supporters are re-parked as traceable wrappers, so the pass that
        authenticates runs the recording ones; the skipped are only
        recorded, the pass that authenticates never reads them.
        """
        supports = await self._listener.supports(request)
        state = security_state_of(state_bag_of(request))
        skipped = state.attributes.get(SecurityRequestAttributes.SKIPPED_AUTHENTICATORS)
        supported = state.attributes.get(SecurityRequestAttributes.AUTHENTICATORS)
        recorded_skipped = _traceable(skipped)
        recorded_supported = _traceable(supported)
        self._authenticators.extend(recorded_skipped)
        self._authenticators.extend(recorded_supported)
        state.attributes[SecurityRequestAttributes.AUTHENTICATORS] = recorded_supported
        return supports

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Pass through, so the wrapped listener authenticates."""
        await self._listener.authenticate(request_event)

    def get_authenticator_manager_listener(self) -> AuthenticatorManagerListener:
        """Return the wrapped listener, the one the wiring really runs."""
        return self._listener

    def get_authenticators_info(self) -> tuple[Mapping[str, object], ...]:
        """Return what each recorded authenticator answered, in the order asked."""
        return tuple(authenticator.get_info() for authenticator in self._authenticators)

    def reset(self) -> None:
        """Drop every recorded authenticator, so the next record starts afresh."""
        self._authenticators = []


def _traceable(parked: object) -> tuple[TraceableAuthenticator, ...]:
    """Return the parked authenticators wrapped for recording, empty when none parked."""
    if not isinstance(parked, tuple):
        return ()
    authenticators = cast("tuple[AuthenticatorInterface, ...]", parked)
    return tuple(
        authenticator
        if isinstance(authenticator, TraceableAuthenticator)
        else TraceableAuthenticator(authenticator)
        for authenticator in authenticators
    )
