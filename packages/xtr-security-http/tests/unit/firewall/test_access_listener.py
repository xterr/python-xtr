"""The access listener parks what a matched rule requires, then decides it over the request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import RequestEvent
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authorization import AccessDecisionManager, RoleVoter
from xtr_security_core.authorization.access_decision import AccessDecision
from xtr_security_core.authorization.voter.authenticated_voter import AuthenticatedVoter
from xtr_security_core.exception import AccessDeniedError, InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.access_map import AccessMap
from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.exception import MissingStateBagError
from xtr_security_http.firewall.access_listener import AccessListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

pytestmark = pytest.mark.anyio


@final
class _RecordingDecisionManager:
    """Answers what it was built to, recording every decide call's arguments."""

    def __init__(self, *, granted: bool) -> None:
        self._granted = granted
        self.calls: list[tuple[TokenInterface, tuple[object, ...], object, AccessDecision]] = []

    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Record the ask, and answer the granted flag this manager was built with."""
        decision = access_decision if access_decision is not None else AccessDecision()
        self.calls.append((token, tuple(attributes), subject, decision))
        decision.is_granted = self._granted
        return self._granted


def _listener(
    *rules: tuple[str, str],
    storage: TokenStorage | None = None,
    manager: AccessDecisionManagerInterface | None = None,
) -> AccessListener:
    access_map = AccessMap()
    for path, attribute in rules:
        access_map.add(PathRequestMatcher(path), attribute)
    return AccessListener(
        storage if storage is not None else TokenStorage(),
        manager if manager is not None else AccessDecisionManager([RoleVoter()]),
        access_map,
    )


def _asked(bag: dict[str, object], path: str = "/api/books") -> ServerRequestInterface:
    """Return a request carrying the event's state bag, as the chain's caller asks about it."""
    return make_message(path=path).with_attribute(SecurityRequestAttributes.STATE_BAG, bag)


def _token(roles: tuple[str, ...]) -> PostAuthenticationToken:
    return PostAuthenticationToken(InMemoryUser("alice"), "api", list(roles))


def test_it_satisfies_the_interface() -> None:
    assert isinstance(_listener(), FirewallListenerInterface)


def test_its_priority_is_after_authentication() -> None:
    assert AccessListener.get_priority() == -255


def test_the_vestigial_flag_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="exception_on_no_token"):
        _ = AccessListener(
            TokenStorage(), AccessDecisionManager([]), AccessMap(), exception_on_no_token=True
        )


async def test_supports_parks_the_matched_attributes_and_answers_true() -> None:
    bag: dict[str, object] = {}
    listener = _listener((r"^/api", "ROLE_USER"))

    answer = await listener.supports(_asked(bag))

    assert answer is True
    assert security_state_of(bag).attributes[
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES
    ] == ("ROLE_USER",)


async def test_supports_answers_none_for_a_public_only_rule() -> None:
    bag: dict[str, object] = {}
    listener = _listener((r"^/api", AuthenticatedVoter.PUBLIC_ACCESS))

    answer = await listener.supports(_asked(bag))

    assert answer is None
    assert security_state_of(bag).attributes[
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES
    ] == (AuthenticatedVoter.PUBLIC_ACCESS,)


async def test_supports_answers_none_when_no_rule_matches() -> None:
    bag: dict[str, object] = {}
    listener = _listener((r"^/admin", "ROLE_ADMIN"))

    answer = await listener.supports(_asked(bag, path="/public"))

    assert answer is None
    assert (
        security_state_of(bag).attributes[SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES] == ()
    )


async def test_supports_refuses_a_request_no_state_bag_was_parked_on() -> None:
    with pytest.raises(MissingStateBagError):
        _ = await _listener().supports(make_message())


async def test_authenticate_decides_the_parked_attributes_with_the_request_as_the_subject() -> None:
    bag: dict[str, object] = {}
    storage = TokenStorage()
    token = _token(("ROLE_USER",))
    storage.set_token(token)
    manager = _RecordingDecisionManager(granted=True)
    listener = _listener((r"^/api", "ROLE_USER"), storage=storage, manager=manager)
    request = _asked(bag)
    _ = await listener.supports(request)

    await listener.authenticate(RequestEvent(request, bag))

    (decided_token, attributes, subject, decision), *rest = manager.calls
    assert not rest
    assert decided_token is token
    assert attributes == ("ROLE_USER",)
    assert subject is request
    assert decision.is_granted is True


async def test_authenticate_removes_the_parked_attributes() -> None:
    bag: dict[str, object] = {}
    listener = _listener((r"^/api", "ROLE_USER"), manager=_RecordingDecisionManager(granted=True))
    request = _asked(bag)
    _ = await listener.supports(request)

    await listener.authenticate(RequestEvent(request, bag))

    assert (
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES not in security_state_of(bag).attributes
    )


async def test_authenticate_skips_when_nothing_is_parked() -> None:
    manager = _RecordingDecisionManager(granted=True)
    listener = _listener((r"^/api", "ROLE_USER"), manager=manager)

    await listener.authenticate(RequestEvent(make_message(path="/api/books"), {}))

    assert manager.calls == []


async def test_authenticate_falls_back_to_a_null_token_when_the_storage_is_empty() -> None:
    bag: dict[str, object] = {}
    manager = _RecordingDecisionManager(granted=True)
    listener = _listener((r"^/api", "ROLE_USER"), manager=manager)
    request = _asked(bag)
    _ = await listener.supports(request)

    await listener.authenticate(RequestEvent(request, bag))

    (token, _attributes, _subject, _decision), *rest = manager.calls
    assert not rest
    assert isinstance(token, NullToken)


async def test_a_refused_decision_raises_carrying_the_whole_refusal() -> None:
    bag: dict[str, object] = {}
    listener = _listener((r"^/api", "ROLE_ADMIN"))
    request = _asked(bag)
    _ = await listener.supports(request)

    with pytest.raises(AccessDeniedError) as raised:
        await listener.authenticate(RequestEvent(request, bag))

    error = raised.value
    assert error.attributes == ("ROLE_ADMIN",)
    assert error.subject is request
    assert error.access_decision is not None
    assert error.access_decision.is_granted is False
    assert "Access to the requested resource is denied." in str(error)
    assert error.access_decision.message in str(error)


async def test_a_public_only_rule_is_decided_and_granted_on_the_chain_path() -> None:
    bag: dict[str, object] = {}
    # The authenticated voter — part of every wired stack — is the one that
    # grants public access; the default RoleVoter-only stack here would not.
    listener = _listener(
        (r"^/api", AuthenticatedVoter.PUBLIC_ACCESS),
        manager=AccessDecisionManager(
            [AuthenticatedVoter(AuthenticationTrustResolver()), RoleVoter()],
        ),
    )
    request = _asked(bag)
    _ = await listener.supports(request)

    await listener.authenticate(RequestEvent(request, bag))


async def test_check_access_passes_a_granted_rule() -> None:
    listener = _listener((r"^/api", "ROLE_USER"))

    await listener.check_access(make_message(path="/api/books"), _token(("ROLE_USER",)))


async def test_check_access_refuses_a_denied_rule() -> None:
    listener = _listener((r"^/api", "ROLE_ADMIN"))

    with pytest.raises(AccessDeniedError):
        await listener.check_access(make_message(path="/api/books"), _token(("ROLE_USER",)))


async def test_check_access_short_circuits_a_public_access_rule() -> None:
    manager = _RecordingDecisionManager(granted=True)
    listener = _listener((r"^/api", AuthenticatedVoter.PUBLIC_ACCESS), manager=manager)

    await listener.check_access(make_message(path="/api/books"), NullToken())

    assert manager.calls == []


async def test_check_access_leaves_a_request_matching_no_rule_alone() -> None:
    manager = _RecordingDecisionManager(granted=True)
    listener = _listener((r"^/admin", "ROLE_ADMIN"), manager=manager)

    await listener.check_access(make_message(path="/public"), NullToken())

    assert manager.calls == []
