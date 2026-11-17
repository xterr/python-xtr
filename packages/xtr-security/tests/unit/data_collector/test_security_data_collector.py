"""The security panel keeps the firewall, the token, the authenticators and the decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import anyio
import pytest
from typing_extensions import override
from xtr_clock import MockClock
from xtr_http_kernel.data_collector import (
    LateDataCollectorInterface,
    ProfiledRequest,
    TracingDataCollectorInterface,
)
from xtr_security_core import (
    AccessDecisionManager,
    InMemoryUser,
    NullToken,
    RoleVoter,
    SwitchUserToken,
    TraceableAccessDecisionManager,
    UsernamePasswordToken,
)
from xtr_security_core.exception import BadCredentialsError
from xtr_security_http import SecurityRequestAttributes, TraceableAuthenticator
from xtr_security_http._security_state import SecurityState
from xtr_security_http.authenticator.abstract_authenticator import AbstractAuthenticator
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.authenticator.passport.passport import Passport

from tests.support.messages import make_message
from xtr_security.bundle.firewall_context import FirewallContext
from xtr_security.data_collector import SecurityDataCollector

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core import TokenInterface
    from xtr_security_core.authorization.voter import Access, Vote
    from xtr_security_http.authentication.authenticator_manager_interface import (
        AuthenticatorManagerInterface,
    )
    from xtr_security_http.firewall.access_listener import AccessListener

pytestmark = pytest.mark.anyio


@final
class _ReportingVoter:
    """A role voter that reports its vote to a traceable manager, as the vote listener does."""

    def __init__(self) -> None:
        self.traceable: TraceableAccessDecisionManager | None = None
        self._role_voter = RoleVoter()

    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        result = await self._role_voter.vote(token, subject, attributes, vote)
        if self.traceable is not None:
            self.traceable.add_voter_vote(self, attributes, result, ["a reason"])
        return result


@final
class _PasswordAuthenticator(AbstractAuthenticator):
    """Builds a password passport, taking a quarter second on the clock it is given."""

    def __init__(self, clock: MockClock) -> None:
        self._clock = clock

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        return True

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        self._clock.sleep(0.25)
        return Passport(UserBadge("alice"), PasswordCredentials("hunter2"))


def _collector() -> SecurityDataCollector:
    return SecurityDataCollector(votes_traced=True, authenticators_traced=True)


def _profiled(state: SecurityState | None = None) -> ProfiledRequest:
    bag: dict[str, object] = {}
    if state is not None:
        bag[SecurityRequestAttributes.SECURITY_STATE] = state
    return ProfiledRequest(make_message(), 200, {}, bag)


def _context(name: str = "api") -> FirewallContext:
    return FirewallContext(
        name,
        cast("AuthenticatorManagerInterface", object()),
        cast("AccessListener", object()),
    )


def _user_token() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])


def _traceable(collector: SecurityDataCollector) -> TraceableAccessDecisionManager:
    voter = _ReportingVoter()
    traceable = TraceableAccessDecisionManager(
        AccessDecisionManager([voter]), collector.record_decision
    )
    voter.traceable = traceable
    return traceable


def test_it_is_a_tracing_late_collector_named_security() -> None:
    collector = _collector()

    assert collector.name == "security"
    assert isinstance(collector, TracingDataCollectorInterface)
    assert isinstance(collector, LateDataCollectorInterface)


def test_a_request_no_firewall_claimed_is_not_secured() -> None:
    data = _collector().collect(_profiled())

    assert data == {
        "enabled": False,
        "firewall": None,
        "token": None,
        "votes_traced": True,
        "authenticators_traced": True,
    }


def test_the_firewall_that_ran_is_kept() -> None:
    state = SecurityState()
    state.firewall_context = _context()

    data = _collector().collect(_profiled(state))

    assert data["enabled"] is True
    assert data["firewall"] == {
        "name": "api",
        "security": True,
        "entry_point": None,
        "access_denied_handler": None,
        "listeners": [],
        "logout": False,
    }


def test_the_token_is_kept_without_its_credentials() -> None:
    state = SecurityState()
    state.token = _user_token()

    token = cast("dict[str, object]", _collector().collect(_profiled(state))["token"])

    assert token == {
        "class": f"{UsernamePasswordToken.__module__}.UsernamePasswordToken",
        "user_identifier": "alice",
        "roles": ["ROLE_USER"],
        "authenticated": True,
        "impersonated": False,
        "impersonator": None,
    }


def test_an_anonymous_token_is_not_authenticated() -> None:
    state = SecurityState()
    state.token = NullToken()

    token = cast("dict[str, object]", _collector().collect(_profiled(state))["token"])

    assert token["authenticated"] is False
    assert token["user_identifier"] == ""


def test_a_switched_user_names_the_impersonator() -> None:
    state = SecurityState()
    state.token = SwitchUserToken(InMemoryUser("bob"), "api", ["ROLE_USER"], _user_token())

    token = cast("dict[str, object]", _collector().collect(_profiled(state))["token"])

    assert (token["impersonated"], token["impersonator"]) == (True, "alice")


async def test_each_decision_is_kept_with_every_vote() -> None:
    collector = _collector()
    traceable = _traceable(collector)
    collector.begin_request()

    _ = await traceable.decide(_user_token(), ["ROLE_ADMIN"], {"isbn": "1", "token": "abc"})
    data = collector.late_collect({}, _profiled())

    (decision,) = cast("list[dict[str, object]]", data["decisions"])
    assert decision["attributes"] == ["ROLE_ADMIN"]
    assert decision["result"] is False
    assert decision["strategy"] == "affirmative"
    assert decision["voters"] == [
        {
            "voter": f"{__name__}._ReportingVoter",
            "attributes": ["ROLE_ADMIN"],
            "vote": "denied",
            "reasons": ["a reason"],
        }
    ]
    subject = cast("dict[str, object]", decision["subject"])
    assert subject["items"] == [
        [
            {"kind": "str", "type": "str", "value": "isbn", "truncated": 0},
            {"kind": "str", "type": "str", "value": "1", "truncated": 0},
        ],
        [
            {"kind": "str", "type": "str", "value": "token", "truncated": 0},
            {"kind": "str", "type": "str", "value": "******", "truncated": 0},
        ],
    ]
    assert data["voter_strategy"] == "affirmative"


async def test_a_callable_attribute_is_named_by_its_qualified_name() -> None:
    collector = _collector()
    collector.begin_request()

    def owns(context: object, subject: object) -> bool:
        return context is subject

    collector.record_decision({"attributes": ("ROLE_USER", owns, 7), "object": None})

    (decision,) = cast(
        "list[dict[str, object]]", collector.late_collect({}, _profiled())["decisions"]
    )
    assert decision["attributes"] == [
        "ROLE_USER",
        f"{__name__}.test_a_callable_attribute_is_named_by_its_qualified_name.<locals>.owns",
        "7",
    ]


async def test_a_decision_outside_a_profiled_request_is_not_kept() -> None:
    collector = _collector()
    traceable = _traceable(collector)

    _ = await traceable.decide(_user_token(), ["ROLE_USER"])

    assert collector.late_collect({}, _profiled())["decisions"] == []


def test_without_a_decision_the_strategy_is_unknown() -> None:
    collector = _collector()
    collector.begin_request()

    assert collector.late_collect({}, _profiled())["voter_strategy"] is None


async def test_an_authenticator_is_read_once_it_has_answered() -> None:
    clock = MockClock("2026-01-01 00:00:00")
    collector = _collector()
    collector.begin_request()
    authenticator = TraceableAuthenticator(_PasswordAuthenticator(clock), clock)
    collector.record_authenticator(authenticator)
    request = make_message()

    _ = authenticator.supports(request)
    _ = await authenticator.authenticate(request)
    _ = await authenticator.on_authentication_success(request, _user_token(), "api")
    (recorded,) = cast(
        "list[dict[str, object]]", collector.late_collect({}, _profiled())["authenticators"]
    )

    assert recorded["authenticator"] == f"{__name__}._PasswordAuthenticator"
    assert (recorded["supports"], recorded["authenticated"]) == (True, True)
    assert recorded["unsupported_reasons"] == []
    assert recorded["duration_ms"] == pytest.approx(250.0)
    assert (recorded["error"], recorded["error_class"]) == (None, None)
    passport = cast("dict[str, object]", recorded["passport"])
    assert passport["type"] == "xtr_security_http.authenticator.passport.passport.Passport"
    assert "hunter2" not in repr(passport)


async def test_a_failed_authenticator_keeps_its_error() -> None:
    clock = MockClock()
    collector = _collector()
    collector.begin_request()
    authenticator = TraceableAuthenticator(_PasswordAuthenticator(clock), clock)
    collector.record_authenticator(authenticator)

    _ = await authenticator.on_authentication_failure(
        make_message(), BadCredentialsError("The password is wrong.")
    )
    (recorded,) = cast(
        "list[dict[str, object]]", collector.late_collect({}, _profiled())["authenticators"]
    )

    assert recorded["authenticated"] is False
    assert recorded["error"] == "The password is wrong."
    assert (
        recorded["error_class"]
        == "xtr_security_core.exception.bad_credentials_error.BadCredentialsError"
    )
    assert (recorded["duration_ms"], recorded["passport"]) == (None, None)


async def test_concurrent_requests_each_keep_their_own_decisions() -> None:
    collector = _collector()
    traceable = _traceable(collector)
    seen: dict[str, list[str]] = {}

    async def serve(role: str) -> None:
        collector.begin_request()
        _ = await traceable.decide(_user_token(), [role])
        await anyio.lowlevel.checkpoint()
        _ = await traceable.decide(_user_token(), [role])
        decisions = cast(
            "list[dict[str, object]]", collector.late_collect({}, _profiled())["decisions"]
        )
        seen[role] = [cast("list[str]", decision["attributes"])[0] for decision in decisions]

    async with anyio.create_task_group() as group:
        for role in ("ROLE_A", "ROLE_B", "ROLE_C"):
            _ = group.start_soon(serve, role)

    assert seen == {role: [role, role] for role in ("ROLE_A", "ROLE_B", "ROLE_C")}


async def test_a_decision_recorded_from_a_worker_thread_joins_its_request() -> None:
    collector = _collector()
    collector.begin_request()

    await anyio.to_thread.run_sync(
        collector.record_decision, {"attributes": ("ROLE_USER",), "object": None}
    )

    (decision,) = cast(
        "list[dict[str, object]]", collector.late_collect({}, _profiled())["decisions"]
    )
    assert decision["attributes"] == ["ROLE_USER"]
    assert (decision["result"], decision["strategy"], decision["voters"]) == (None, None, [])
