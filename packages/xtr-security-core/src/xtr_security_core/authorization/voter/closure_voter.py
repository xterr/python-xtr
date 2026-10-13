"""A voter that allows using a callable as the attribute being voted on."""

from __future__ import annotations

from inspect import isawaitable
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_core.authorization.authorization_checker_interface import (
    AuthorizationCheckerInterface,
)
from xtr_security_core.authorization.is_granted_context import IsGrantedContext
from xtr_security_core.exception import InvalidArgumentError

from .access import Access
from .cacheable_voter_interface import CacheableVoterInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision import AccessDecision
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

    from .vote import Vote

__all__ = ["ClosureVoter"]


@final
class ClosureVoter(CacheableVoterInterface):
    """Grants an attribute that is itself the check: a callable.

    Where a role is a string to match, a closure is a decision to run. The
    attribute is a callable taking an
    :class:`~xtr_security_core.authorization.is_granted_context.IsGrantedContext`
    and the subject, and answering true or false — synchronously or not. It
    covers the checks too specific for a reusable voter ("is this token the
    owner of this order?") without an expression language.

    Each closure's nested questions are decided against the same token, each in
    a decision of its own, so the voter can report the reasons they gave and
    forward a re-authentication one of them requested. The voter needs the
    decision manager for that; the manager binds itself when it is built from
    a voter list containing this one.
    """

    __slots__ = ("_manager",)

    _manager: AccessDecisionManagerInterface | None

    def __init__(self) -> None:
        """Start unbound; the decision manager binds itself when it is built."""
        self._manager = None

    def bind_manager(self, manager: AccessDecisionManagerInterface) -> None:
        """Record the decision manager a closure's nested questions are decided by.

        Raises:
            InvalidArgumentError: When already bound to a different manager,
                which would silently route a shared voter's nested questions to
                whichever manager was built last.
        """
        if self._manager is not None and self._manager is not manager:
            raise InvalidArgumentError(
                "This closure voter is already bound to a different decision manager.",
            )
        self._manager = manager

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Never vote on a string attribute: the attributes read here are callables."""
        del attribute
        return False

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject."""
        del subject_type
        return True

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Run each callable attribute: grant on the first that returns true.

        Raises:
            InvalidArgumentError: When the voter was never bound to a decision
                manager.
        """
        # Imported here: the nested checker reads the access decision, whose
        # module imports this package — a top-level import would be circular.
        from xtr_security_core.authorization.nested_authorization_checker import (  # noqa: PLC0415
            NestedAuthorizationChecker,
        )

        failing_closures: list[str] = []
        result = Access.ABSTAIN
        re_authentication_attribute: str | None = None
        for attribute in attributes:
            if not callable(attribute):
                continue

            name = _closure_name(attribute)
            result = Access.DENIED
            authorization_checker = NestedAuthorizationChecker(
                _TokenAuthorizationChecker(token, self._bound_manager()),
            )

            closure = cast(
                "Callable[[IsGrantedContext, object], bool | Awaitable[bool]]", attribute
            )
            outcome = closure(
                IsGrantedContext(token, token.get_user(), authorization_checker),
                subject,
            )
            if isawaitable(outcome):
                outcome = await outcome
            if outcome:
                if vote is not None:
                    authorization_checker.add_reasons(vote, is_granted=True)
                    vote.add_reason(f"Closure {name} returned true.")
                return Access.GRANTED

            if vote is not None:
                authorization_checker.add_reasons(vote, is_granted=False)

            failing_closures.append(name)
            if re_authentication_attribute is None:
                re_authentication_attribute = authorization_checker.re_authentication_attribute

        if failing_closures and vote is not None:
            plural = "s" if len(failing_closures) > 1 else ""
            vote.add_reason(f"Closure{plural} {', '.join(failing_closures)} returned false.")

        if re_authentication_attribute is not None and vote is not None:
            vote.request_re_authentication(re_authentication_attribute)

        return result

    def _bound_manager(self) -> AccessDecisionManagerInterface:
        """Return the bound decision manager.

        Raises:
            InvalidArgumentError: When the voter was never bound to one.
        """
        if self._manager is None:
            raise InvalidArgumentError(
                "This closure voter was never bound to a decision manager.",
            )
        return self._manager


@final
class _TokenAuthorizationChecker(AuthorizationCheckerInterface):
    """Decides every question for one token, the one the closure was run for."""

    __slots__ = ("_manager", "_token")

    def __init__(self, token: TokenInterface, manager: AccessDecisionManagerInterface) -> None:
        self._token = token
        self._manager = manager

    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Decide ``attribute`` over ``subject`` for the closure's token."""
        return await self._manager.decide(self._token, [attribute], subject, access_decision)


def _closure_name(closure: object) -> str:
    """Name a callable the way a reason reports it."""
    name = getattr(closure, "__name__", None)
    if isinstance(name, str):
        return name
    return type(closure).__name__
