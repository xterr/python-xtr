"""Blocking a transition when a guard configured on it refuses."""

from __future__ import annotations

# No import here is for the type checker only: a container builds this listener
# from its constructor's annotations, and registering ``on_transition`` as a
# listener reads that method's.
import inspect
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from typing import final

from xtr_security_core.authentication import AuthenticationTrustResolverInterface
from xtr_security_core.authentication.token.storage import TokenStorageInterface
from xtr_security_core.authorization import AuthorizationCheckerInterface
from xtr_security_core.role import RoleHierarchyInterface

from xtr_workflow.event import GuardEvent
from xtr_workflow.transition import Transition
from xtr_workflow.transition_blocker import TransitionBlocker

from .guard_context import GuardContext
from .guard_expression import GuardExpression

__all__ = ["GuardListener"]


@final
class GuardListener:
    """Runs the guards configured for a guard event; each one refusing blocks the transition.

    The configuration maps the name a guard event is dispatched under — a
    workflow's guard event narrowed to a transition — to the guards to run for
    it. A guard expression runs only for the transition it was configured on,
    since every transition sharing a name is guarded under the same event name;
    a bare guard runs for any. Every guard runs, and each refusal adds a
    blocker naming the guard, so the caller learns every reason at once.

    What a guard is handed comes from the security services: the current token,
    its user, the roles it reaches, and the checkers to ask about it. A guard
    cannot run without them, so the listener takes them all.
    """

    __slots__: tuple[str, ...] = (
        "_authorization_checker",
        "_configuration",
        "_role_hierarchy",
        "_token_storage",
        "_trust_resolver",
    )

    _configuration: Mapping[
        str, Sequence[GuardExpression | Callable[[GuardContext], bool | Awaitable[bool]]]
    ]
    _token_storage: TokenStorageInterface
    _authorization_checker: AuthorizationCheckerInterface
    _trust_resolver: AuthenticationTrustResolverInterface
    _role_hierarchy: RoleHierarchyInterface

    def __init__(
        self,
        configuration: Mapping[
            str, Sequence[GuardExpression | Callable[[GuardContext], bool | Awaitable[bool]]]
        ],
        token_storage: TokenStorageInterface,
        authorization_checker: AuthorizationCheckerInterface,
        trust_resolver: AuthenticationTrustResolverInterface,
        role_hierarchy: RoleHierarchyInterface,
    ) -> None:
        """Run the guards of ``configuration``, handing each the security services' view.

        Args:
            configuration: The guards to run, by the name of the guard event
                they run for: guard expressions, or bare guards.
            token_storage: Where the token of whoever is moving the subject is.
            authorization_checker: Handed to the guards, to ask whether that
                token is granted an attribute.
            trust_resolver: Handed to the guards, to ask how strongly the token
                was authenticated.
            role_hierarchy: Expands the token's roles into every role they
                reach, for the guards to read.
        """
        self._configuration = configuration
        self._token_storage = token_storage
        self._authorization_checker = authorization_checker
        self._trust_resolver = trust_resolver
        self._role_hierarchy = role_hierarchy

    async def on_transition(self, event: GuardEvent, event_name: str) -> None:
        """Run the guards configured for ``event_name`` that apply to the event's transition.

        Args:
            event: The guard event, which a refusing guard blocks.
            event_name: The name the event was dispatched under, which picks
                the guards.
        """
        for guard in self._guards_for(event_name, event.get_transition()):
            await self._validate_guard_expression(event, guard)

    def get_guard_names(self, event_name: str, transition: Transition) -> list[str]:
        """Return the name of each guard run for ``transition`` under ``event_name``, in order.

        Each is named as a blocker names it, so a tool listing what this
        listener asks before a transition shows the names its refusals carry.
        """
        return [_qualified_name(guard) for guard in self._guards_for(event_name, transition)]

    def _guards_for(
        self, event_name: str, transition: Transition
    ) -> Iterator[Callable[[GuardContext], bool | Awaitable[bool]]]:
        """Yield the guards configured for ``event_name`` that apply to ``transition``.

        A guard expression applies to the transition it was configured on
        only; a bare guard, to any.
        """
        for guard in self._configuration.get(event_name, ()):
            match guard:
                case GuardExpression():
                    if guard.get_transition() is transition:
                        yield guard.get_expression()
                case _:
                    yield guard

    async def _validate_guard_expression(
        self,
        event: GuardEvent,
        guard: Callable[[GuardContext], bool | Awaitable[bool]],
    ) -> None:
        """Block the event's transition if ``guard`` refuses it, naming the guard."""
        outcome = guard(self._guard_context(event))
        if inspect.isawaitable(outcome):
            outcome = await outcome
        if not outcome:
            event.add_transition_blocker(
                TransitionBlocker.create_blocked_by_expression_guard_listener(
                    _qualified_name(guard)
                )
            )

    def _guard_context(self, event: GuardEvent) -> GuardContext:
        """Return what a guard is handed: the subject, and the current token as security sees it."""
        token = self._token_storage.get_token()
        if token is None:
            return GuardContext(
                subject=event.get_subject(),
                token=None,
                user=None,
                role_names=(),
                authorization_checker=self._authorization_checker,
                trust_resolver=self._trust_resolver,
            )

        return GuardContext(
            subject=event.get_subject(),
            token=token,
            user=token.get_user(),
            role_names=tuple(self._role_hierarchy.get_reachable_role_names(token.get_role_names())),
            authorization_checker=self._authorization_checker,
            trust_resolver=self._trust_resolver,
        )


def _qualified_name(guard: Callable[[GuardContext], bool | Awaitable[bool]]) -> str:
    """Return ``guard`` as a blocker names it: its module, then its qualified name.

    A function or a method has both; a callable object is named by its class.
    """
    module: object = getattr(guard, "__module__", None)
    qualified_name: object = getattr(guard, "__qualname__", None)
    if isinstance(module, str) and isinstance(qualified_name, str):
        return f"{module}.{qualified_name}"

    guard_class = type(guard)
    return f"{guard_class.__module__}.{guard_class.__qualname__}"
