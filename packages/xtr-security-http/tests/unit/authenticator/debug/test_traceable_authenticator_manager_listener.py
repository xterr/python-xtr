"""The traceable manager listener records what the wrapped one's passes chose."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import StarletteHttpFactory
from xtr_http_message import Response as PureResponse

from tests.support.messages import make_message
from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator
from xtr_security_http.authenticator.debug.traceable_authenticator_manager_listener import (
    TraceableAuthenticatorManagerListener,
)
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.firewall.authenticator_manager_listener import AuthenticatorManagerListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


@final
class _Authenticator(AbstractAuthenticator):
    """An authenticator whose supports answer is fixed at birth."""

    def __init__(self, *, supports: bool | None = True) -> None:
        self._supports = supports

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return self._supports

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        del request
        return SelfValidatingPassport(UserBadge("alice"))


@final
class _Manager:
    """Parks the two lists a supports pass leaves, like the real manager does."""

    def __init__(
        self, *, skipped: tuple[object, ...] = (), supporters: tuple[object, ...] = ()
    ) -> None:
        self._skipped = skipped
        self._supporters = supporters
        self.supports_calls = 0
        self.authenticate_calls = 0

    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        """Record the ask, parking the lists on the request's carrier."""
        del request
        self.supports_calls += 1
        state.attributes[SecurityRequestAttributes.SKIPPED_AUTHENTICATORS] = self._skipped
        state.attributes[SecurityRequestAttributes.AUTHENTICATORS] = self._supporters
        return bool(self._supporters)

    async def authenticate_request(
        self, request: ServerRequestInterface, state: SecurityState
    ) -> ResponseInterface | None:
        """Record the ask, answering nothing."""
        del request, state
        self.authenticate_calls += 1
        return PureResponse(204, None, None, "1.1")


def _wrapped(
    manager: _Manager,
) -> AuthenticatorManagerListener:
    return AuthenticatorManagerListener(manager, StarletteHttpFactory())


def _asked(bag: dict[str, object]) -> ServerRequestInterface:
    """Return a request carrying the event's state bag, as the chain's caller asks about it."""
    return make_message().with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def test_it_satisfies_the_interface() -> None:
    wrapped = _wrapped(_Manager())
    assert isinstance(TraceableAuthenticatorManagerListener(wrapped), FirewallListenerInterface)


def test_its_priority_is_the_chains_default() -> None:
    assert TraceableAuthenticatorManagerListener.get_priority() == 0


async def test_supports_delegates_to_the_wrapped_listener() -> None:
    manager = _Manager(supporters=(_Authenticator(),))
    bag: dict[str, object] = {}

    answer = await TraceableAuthenticatorManagerListener(_wrapped(manager)).supports(_asked(bag))

    assert answer is True
    assert manager.supports_calls == 1


async def test_supports_reparks_the_supporters_as_traceable_wrappers() -> None:
    supporter = _Authenticator()
    bag: dict[str, object] = {}
    state = security_state_of(bag)

    _ = await TraceableAuthenticatorManagerListener(
        _wrapped(_Manager(supporters=(supporter,)))
    ).supports(_asked(bag))

    reparked = state.attributes[SecurityRequestAttributes.AUTHENTICATORS]
    assert isinstance(reparked, tuple)
    (recorded,) = cast("tuple[TraceableAuthenticator, ...]", reparked)
    assert recorded.get_authenticator() is supporter


async def test_supports_records_the_skipped_without_reparking_them() -> None:
    skipped = _Authenticator(supports=False)
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    listener = TraceableAuthenticatorManagerListener(_wrapped(_Manager(skipped=(skipped,))))

    _ = await listener.supports(_asked(bag))

    assert state.attributes[SecurityRequestAttributes.SKIPPED_AUTHENTICATORS] == (skipped,)
    assert len(listener.get_authenticators_info()) == 1


async def test_supports_keeps_an_already_traceable_authenticator_as_it_is() -> None:
    already = TraceableAuthenticator(_Authenticator())
    bag: dict[str, object] = {}
    state = security_state_of(bag)

    _ = await TraceableAuthenticatorManagerListener(
        _wrapped(_Manager(supporters=(already,)))
    ).supports(_asked(bag))

    reparked = state.attributes[SecurityRequestAttributes.AUTHENTICATORS]
    assert isinstance(reparked, tuple)
    (kept,) = cast("tuple[TraceableAuthenticator, ...]", reparked)
    assert kept is already


async def test_authenticate_delegates_to_the_wrapped_listener() -> None:
    manager = _Manager()
    bag: dict[str, object] = {}
    event = RequestEvent(make_message(), bag)

    await TraceableAuthenticatorManagerListener(_wrapped(manager)).authenticate(event)

    assert manager.authenticate_calls == 1
    assert event.response is not None
    assert event.response.status_code == 204


def test_get_authenticator_manager_listener_returns_the_listener_as_given() -> None:
    wrapped = _wrapped(_Manager())

    assert (
        TraceableAuthenticatorManagerListener(wrapped).get_authenticator_manager_listener()
        is wrapped
    )


async def test_get_authenticators_info_maps_each_recorded_authenticators_info() -> None:
    skipped = _Authenticator(supports=False)
    supporter = _Authenticator()
    listener = TraceableAuthenticatorManagerListener(
        _wrapped(_Manager(skipped=(skipped,), supporters=(supporter,)))
    )
    bag: dict[str, object] = {}
    _ = await listener.supports(_asked(bag))
    reparked = security_state_of(bag).attributes[SecurityRequestAttributes.AUTHENTICATORS]
    assert isinstance(reparked, tuple)
    (wrapper,) = cast("tuple[TraceableAuthenticator, ...]", reparked)

    infos = listener.get_authenticators_info()

    assert len(infos) == 2
    assert infos[1] == wrapper.get_info()


async def test_reset_drops_the_recorded_authenticators() -> None:
    listener = TraceableAuthenticatorManagerListener(
        _wrapped(_Manager(supporters=(_Authenticator(),)))
    )
    bag: dict[str, object] = {}
    _ = await listener.supports(_asked(bag))

    listener.reset()

    assert listener.get_authenticators_info() == ()
