"""A decision manager that logs every decision and the votes behind it."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

from typing_extensions import override

from .access_decision import AccessDecision
from .access_decision_manager_interface import AccessDecisionManagerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .voter.access import Access
    from .voter.voter_interface import VoterInterface

__all__ = ["TraceableAccessDecisionManager"]

#: The logs being filled on the current task, innermost last, each with the
#: manager that opened it and its list of votes — a stack, since a voter may
#: ask for a decision while one is being made.
_current_logs: ContextVar[
    tuple[
        tuple[TraceableAccessDecisionManager, dict[str, object], list[dict[str, object]]],
        ...,
    ]
] = ContextVar("xtr_security_traceable_decision_logs", default=())

#: The decision records in progress on the current task, innermost last, each
#: paired with the manager that opened it.
_access_decision_stack: ContextVar[
    tuple[tuple[TraceableAccessDecisionManager, AccessDecision], ...]
] = ContextVar("xtr_security_traceable_access_decision_stack", default=())


class TraceableAccessDecisionManager(AccessDecisionManagerInterface):
    """Decorates a decision manager to log the voters and the decisions they made.

    Each decision is logged with its attributes, its subject, the votes cast —
    fed through :meth:`add_voter_vote` by whatever listens to the votes — and
    its result. Meant for one unit of work: the log grows with every decision,
    so the manager is built per request and :meth:`reset` between them.

    A decision a closure asks for is made by the decorated manager directly,
    so it is not logged as a decision of its own; the votes it collects are
    still fed into the decision in progress.
    """

    __slots__: tuple[str, ...] = ("_decision_log", "_manager", "_strategy", "_voters")

    _manager: AccessDecisionManagerInterface
    _strategy: str | None
    _voters: dict[type, VoterInterface]
    _decision_log: list[dict[str, object]]

    def __init__(self, manager: AccessDecisionManagerInterface) -> None:
        """Wrap ``manager``, starting with an empty log."""
        self._manager = manager
        self._strategy = None
        self._voters = {}
        self._decision_log = []

    @override
    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Decide through the decorated manager, logging the decision."""
        voter_details: list[dict[str, object]] = []
        current_log: dict[str, object] = {
            "attributes": tuple(attributes),
            "object": subject,
            "voter_details": voter_details,
        }
        logs_reset = _current_logs.set((*_current_logs.get(), (self, current_log, voter_details)))

        if access_decision is None:
            access_decision = self._innermost_access_decision() or AccessDecision()
        stack_reset = _access_decision_stack.set(
            (*_access_decision_stack.get(), (self, access_decision))
        )

        decided = False
        try:
            access_decision.is_granted = await self._manager.decide(
                token, attributes, subject, access_decision
            )
            decided = True
            return access_decision.is_granted
        finally:
            _access_decision_stack.reset(stack_reset)
            self._strategy = access_decision.strategy
            _current_logs.reset(logs_reset)
            if decided:
                current_log["result"] = access_decision.is_granted
            self._decision_log.append(current_log)

    def add_voter_vote(
        self,
        voter: VoterInterface,
        attributes: Sequence[object],
        vote: Access,
        reasons: Sequence[str] = (),
    ) -> None:
        """Record a voter's vote on the decision being logged.

        A vote cast while no decision of this manager is in progress is
        ignored: there is no log entry to attach it to.
        """
        voter_details = self._innermost_voter_details()
        if voter_details is None:
            return
        voter_details.append(
            {
                "voter": voter,
                "attributes": tuple(attributes),
                "vote": vote,
                "reasons": tuple(reasons),
            },
        )
        self._voters[type(voter)] = voter

    def get_strategy(self) -> str:
        """Return the name of the strategy that made the last decision, or ``"-"``."""
        return self._strategy if self._strategy is not None else "-"

    def get_voters(self) -> Sequence[VoterInterface]:
        """Return each voter that voted, one per voter class."""
        return tuple(self._voters.values())

    def get_decision_log(self) -> Sequence[dict[str, object]]:
        """Return every finished decision, in the order it finished."""
        return tuple(self._decision_log)

    def reset(self) -> None:
        """Forget the strategy, the voters and the log."""
        self._strategy = None
        self._voters = {}
        self._decision_log = []

    def _innermost_voter_details(self) -> list[dict[str, object]] | None:
        """Return the votes of the innermost log entry this manager is filling, if any."""
        for manager, _, voter_details in reversed(_current_logs.get()):
            if manager is self:
                return voter_details
        return None

    def _innermost_access_decision(self) -> AccessDecision | None:
        """Return the innermost decision record this manager has in progress, if any."""
        for manager, access_decision in reversed(_access_decision_stack.get()):
            if manager is self:
                return access_decision
        return None
