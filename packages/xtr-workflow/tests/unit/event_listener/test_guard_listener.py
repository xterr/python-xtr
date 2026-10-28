"""The guard listener blocks a transition when a guard configured on it refuses.

A guard is a callable handed a guard context, answering at once or through an
awaitable. A guard expression ties one to the transition it was configured on,
among the several a name can have.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, final, get_type_hints

import pytest
from xtr_security_core import (
    AccessDecisionManager,
    AuthenticationTrustResolver,
    AuthorizationChecker,
    InMemoryUser,
    RoleHierarchy,
    RoleVoter,
    TokenStorage,
    TokenStorageInterface,
    UsernamePasswordToken,
)

from tests.fixtures.subject import Subject
from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import Marking, Transition
from xtr_workflow.event import GuardEvent
from xtr_workflow.event_listener import GuardContext, GuardExpression
from xtr_workflow.event_listener.guard_listener import GuardListener

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

pytestmark = pytest.mark.anyio

_Guard: TypeAlias = "GuardExpression | Callable[[GuardContext], bool | Awaitable[bool]]"

EVENT_NAME = "workflow.article.guard.publish"
EXPRESSION_CODE = "326a1e9c-0c12-11e8-ba89-0ed5f89f718b"


@final
class _RecordingGuard:
    """Answers ``outcome`` at once, keeping every context it is asked with."""

    def __init__(self, outcome: bool) -> None:
        self._outcome = outcome
        self.contexts: list[GuardContext] = []

    def __call__(self, context: GuardContext) -> bool:
        self.contexts.append(context)
        return self._outcome


async def _is_granted_admin(context: GuardContext) -> bool:
    return await context.authorization_checker.is_granted("ROLE_ADMIN")


def _refuse(context: GuardContext) -> bool:
    del context
    return False


def _event(transition: Transition | None = None) -> GuardEvent:
    guarded = transition if transition is not None else Transition("name", "from", "to")
    return GuardEvent(Subject(), Marking(), guarded, WorkflowStub())


def _guard_listener(
    configuration: Mapping[str, Sequence[_Guard]], roles: Sequence[str] | None = ("ROLE_USER",)
) -> GuardListener:
    """Return a listener whose token storage holds a token granted ``roles``; none for ``None``."""
    token_storage = TokenStorage()
    if roles is not None:
        user = InMemoryUser("username", "credentials", roles)
        token_storage.set_token(UsernamePasswordToken(user, "provider", roles))
    return GuardListener(
        configuration,
        token_storage,
        AuthorizationChecker(token_storage, AccessDecisionManager([RoleVoter()])),
        AuthenticationTrustResolver(),
        RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]}),
    )


async def test_an_event_name_no_guard_is_configured_for_blocks_nothing() -> None:
    guard = _RecordingGuard(False)
    event = _event()

    await _guard_listener({"test_is_granted": [guard]}).on_transition(event, "not supported")

    assert not event.is_blocked()
    assert guard.contexts == []


async def test_a_guard_the_authorization_checker_refuses_blocks_the_transition() -> None:
    listener = _guard_listener({"test_is_granted": [_is_granted_admin]}, roles=["ROLE_USER"])
    event = _event()

    await listener.on_transition(event, "test_is_granted")

    assert event.is_blocked()


async def test_a_guard_the_authorization_checker_grants_lets_the_transition_through() -> None:
    listener = _guard_listener({"test_is_granted": [_is_granted_admin]}, roles=["ROLE_ADMIN"])
    event = _event()

    await listener.on_transition(event, "test_is_granted")

    assert not event.is_blocked()


async def test_no_guard_expression_runs_for_a_transition_none_was_configured_on() -> None:
    first, second = _RecordingGuard(False), _RecordingGuard(True)
    listener = _guard_listener(
        {
            "test_expression": [
                GuardExpression(Transition("name", "from", "to"), first),
                GuardExpression(Transition("name", "from", "to"), second),
            ]
        }
    )
    event = _event()

    await listener.on_transition(event, "test_expression")

    assert not event.is_blocked()
    assert (first.contexts, second.contexts) == ([], [])


async def test_only_the_guard_expression_of_the_transition_guarded_runs() -> None:
    first, second = _RecordingGuard(False), _RecordingGuard(True)
    guarded = Transition("name", "from", "to")
    listener = _guard_listener(
        {
            "test_expression": [
                GuardExpression(Transition("name", "from", "to"), first),
                GuardExpression(guarded, second),
            ]
        }
    )
    event = _event(guarded)

    await listener.on_transition(event, "test_expression")

    assert not event.is_blocked()
    assert first.contexts == []
    assert len(second.contexts) == 1


async def test_a_guard_expression_refusing_blocks_the_transition_it_guards() -> None:
    first, second = _RecordingGuard(True), _RecordingGuard(False)
    guarded = Transition("name", "from", "to")
    listener = _guard_listener(
        {
            "test_expression": [
                GuardExpression(Transition("name", "from", "to"), first),
                GuardExpression(guarded, second),
            ]
        }
    )
    event = _event(guarded)

    await listener.on_transition(event, "test_expression")

    assert event.is_blocked()
    assert first.contexts == []
    assert len(second.contexts) == 1


async def test_a_guard_is_handed_the_subject_the_token_its_user_and_every_role_it_reaches() -> None:
    user = InMemoryUser("admin", "credentials", ["ROLE_ADMIN"])
    token = UsernamePasswordToken(user, "main", ["ROLE_ADMIN"])
    token_storage = TokenStorage()
    token_storage.set_token(token)
    authorization_checker = AuthorizationChecker(token_storage, AccessDecisionManager())
    trust_resolver = AuthenticationTrustResolver()
    guard = _RecordingGuard(True)
    listener = GuardListener(
        {EVENT_NAME: [guard]},
        token_storage,
        authorization_checker,
        trust_resolver,
        RoleHierarchy({"ROLE_ADMIN": ["ROLE_USER"]}),
    )
    event = _event()

    await listener.on_transition(event, EVENT_NAME)

    assert guard.contexts == [
        GuardContext(
            subject=event.get_subject(),
            token=token,
            user=user,
            role_names=("ROLE_ADMIN", "ROLE_USER"),
            authorization_checker=authorization_checker,
            trust_resolver=trust_resolver,
        )
    ]


async def test_without_a_token_a_guard_is_handed_no_token_no_user_and_no_role() -> None:
    guard = _RecordingGuard(True)

    await _guard_listener({EVENT_NAME: [guard]}, roles=None).on_transition(_event(), EVENT_NAME)

    [context] = guard.contexts
    assert (context.token, context.user, context.role_names) == (None, None, ())


async def test_the_blocker_names_the_refusing_guard_by_its_qualified_name() -> None:
    event = _event()

    await _guard_listener({EVENT_NAME: [_refuse]}).on_transition(event, EVENT_NAME)

    [blocker] = event.get_transition_blocker_list()
    assert blocker.get_code() == EXPRESSION_CODE
    assert blocker.get_parameters() == {
        "expression": "tests.unit.event_listener.test_guard_listener._refuse"
    }


async def test_a_refusing_callable_object_is_named_by_its_class() -> None:
    event = _event()

    await _guard_listener({EVENT_NAME: [_RecordingGuard(False)]}).on_transition(event, EVENT_NAME)

    [blocker] = event.get_transition_blocker_list()
    assert blocker.get_parameters() == {
        "expression": "tests.unit.event_listener.test_guard_listener._RecordingGuard"
    }


async def test_every_refusing_guard_adds_a_blocker_of_its_own() -> None:
    event = _event()
    guards = [_refuse, _RecordingGuard(True), _RecordingGuard(False)]

    await _guard_listener({EVENT_NAME: guards}).on_transition(event, EVENT_NAME)

    assert [blocker.get_parameters() for blocker in event.get_transition_blocker_list()] == [
        {"expression": "tests.unit.event_listener.test_guard_listener._refuse"},
        {"expression": "tests.unit.event_listener.test_guard_listener._RecordingGuard"},
    ]


def test_the_guards_run_for_a_transition_are_named_as_their_blockers_name_them() -> None:
    guarded = Transition("name", "from", "to")
    listener = _guard_listener(
        {
            EVENT_NAME: [
                _refuse,
                GuardExpression(Transition("name", "from", "to"), _is_granted_admin),
                GuardExpression(guarded, _RecordingGuard(True)),
            ]
        }
    )

    names = listener.get_guard_names(EVENT_NAME, guarded)

    assert names == [
        "tests.unit.event_listener.test_guard_listener._refuse",
        "tests.unit.event_listener.test_guard_listener._RecordingGuard",
    ]


def test_an_event_name_no_guard_is_configured_for_names_no_guard() -> None:
    listener = _guard_listener({EVENT_NAME: [_refuse]})

    assert listener.get_guard_names("not supported", Transition("name", "from", "to")) == []


def test_a_container_can_read_what_it_takes_and_what_it_listens_to() -> None:
    constructor = get_type_hints(GuardListener.__init__)
    listener = get_type_hints(GuardListener.on_transition)

    assert constructor["token_storage"] is TokenStorageInterface
    assert listener["event"] is GuardEvent
