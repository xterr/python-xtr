"""A decision manager that logs every decision and the votes behind it."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, final, override

from .access_decision import AccessDecision
from .access_decision_manager_interface import AccessDecisionManagerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .voter.access import Access
    from .voter.voter_interface import VoterInterface

__all__ = ["TraceableAccessDecisionManager"]


@final
class _Logging:
    """A decision being logged: the manager logging it and its votes, open until it returns."""

    __slots__ = ("access_decision", "manager", "open", "voter_details")

    def __init__(
        self,
        manager: TraceableAccessDecisionManager,
        voter_details: list[dict[str, object]],
        access_decision: AccessDecision,
    ) -> None:
        self.manager = manager
        self.voter_details = voter_details
        self.access_decision = access_decision
        self.open = True


#: The decisions being logged on the current task, innermost last — a stack,
#: since a voter may ask for a decision while one is being made. Each closed
#: once its decision returns, so a task a voter started, outliving the
#: decision, votes into no log and joins no record of it.
_current_logs: ContextVar[tuple[_Logging, ...]] = ContextVar(
    "xtr_security_traceable_decision_logs", default=()
)


class TraceableAccessDecisionManager(AccessDecisionManagerInterface):
    """Decorates a decision manager to log the voters and the decisions they made.

    Each decision is logged with its attributes, its subject, the votes cast —
    fed through :meth:`add_voter_vote` by whatever listens to the votes — and
    its result. Meant for one unit of work: the log grows with every decision,
    so the manager is built per request and :meth:`reset` between them.

    A decision a closure asks for is made by the decorated manager directly,
    so it is not logged as a decision of its own; the votes it collects are
    still fed into the decision in progress.

    A ``recorder`` hears of every decision as it finishes, its votes in: the
    log is this manager's, while a recorder keeps the decisions wherever the
    tooling reads them from — the profiler's record of the request, say.
    """

    __slots__: tuple[str, ...] = (
        "_decision_log",
        "_manager",
        "_recorder",
        "_strategy",
        "_voters",
    )

    _manager: AccessDecisionManagerInterface
    _recorder: Callable[[Mapping[str, object]], None] | None
    _strategy: str | None
    _voters: dict[type, VoterInterface]
    _decision_log: list[dict[str, object]]

    def __init__(
        self,
        manager: AccessDecisionManagerInterface,
        recorder: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        """Wrap ``manager``, starting with an empty log.

        Args:
            manager: The manager that decides.
            recorder: Called with each finished decision — its log entry plus
                the ``strategy`` that decided it — or ``None`` to keep the
                log alone.
        """
        self._manager = manager
        self._recorder = recorder
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
        if access_decision is None:
            access_decision = self._innermost_access_decision() or AccessDecision()
        logging = _Logging(self, voter_details, access_decision)
        logs_reset = _current_logs.set((*_current_logs.get(), logging))

        decided = False
        try:
            access_decision.is_granted = await self._manager.decide(
                token, attributes, subject, access_decision
            )
            decided = True
            return access_decision.is_granted
        finally:
            logging.open = False
            self._strategy = access_decision.strategy
            _current_logs.reset(logs_reset)
            if decided:
                current_log["result"] = access_decision.is_granted
            self._decision_log.append(current_log)
            if self._recorder is not None:
                self._recorder({**current_log, "strategy": access_decision.strategy})

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
        """Return the votes of the innermost log entry this manager is still filling, if any."""
        logging = self._innermost_logging()
        return None if logging is None else logging.voter_details

    def _innermost_access_decision(self) -> AccessDecision | None:
        """Return the innermost decision record this manager still has in progress, if any."""
        logging = self._innermost_logging()
        return None if logging is None else logging.access_decision

    def _innermost_logging(self) -> _Logging | None:
        """Return the innermost decision this manager is still logging, if any."""
        for logging in reversed(_current_logs.get()):
            if logging.manager is self and logging.open:
                return logging
        return None
