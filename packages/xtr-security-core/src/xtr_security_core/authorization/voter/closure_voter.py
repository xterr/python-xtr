"""A voter that grants a callable attribute."""

from __future__ import annotations

from inspect import isawaitable
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_security_core.authorization.is_granted_context import IsGrantedContext
from xtr_security_core.exception import InvalidArgumentError

from .voter import Voter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision_manager_interface import (
        AccessDecisionManagerInterface,
    )

    from .vote import Vote

__all__ = ["ClosureVoter"]


@final
class ClosureVoter(Voter):
    """Grants an attribute that is itself the check: a callable.

    Where a role is a string to match, a closure is a decision to run. The
    attribute is a callable taking a
    :class:`~xtr_security_core.authorization.is_granted_context.IsGrantedContext`
    and the subject, and answering true or false — synchronously or not. It
    covers the checks too specific for a reusable voter ("is this token the
    owner of this order?") without an expression language.

    The voter builds the context, so it needs the decision manager to let a
    closure ask nested questions. The manager binds itself when it is built
    from a voter list containing this one.
    """

    _manager: AccessDecisionManagerInterface | None

    def __init__(self) -> None:
        """Start unbound; the decision manager binds itself when it is built."""
        self._manager = None

    def bind_manager(self, manager: AccessDecisionManagerInterface) -> None:
        """Record the decision manager a closure defers nested questions to.

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
    def supports(self, attribute: object, subject: object) -> bool:
        """Tell whether ``attribute`` is a callable this voter can run."""
        del subject
        return callable(attribute)

    @override
    async def vote_on_attribute(
        self,
        attribute: object,
        subject: object,
        token: TokenInterface,
        vote: Vote | None,
    ) -> bool:
        """Run the callable ``attribute`` against a freshly built context."""
        if self._manager is None:
            raise InvalidArgumentError(
                "This closure voter was never bound to a decision manager.",
            )
        context = IsGrantedContext(token=token, user=token.get_user(), _manager=self._manager)
        closure = cast("Callable[[IsGrantedContext, object], bool | Awaitable[bool]]", attribute)
        outcome = closure(context, subject)
        if isawaitable(outcome):
            outcome = await outcome
        granted = bool(outcome)
        if not granted and vote is not None:
            vote.add_reason("The closure attribute did not grant access.")
        return granted
