"""The access decision manager: asks the voters, reduces with a strategy."""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .access_decision import AccessDecision
from .access_decision_manager_interface import AccessDecisionManagerInterface
from .strategy.affirmative_strategy import AffirmativeStrategy
from .voter.cacheable_voter_interface import CacheableVoterInterface
from .voter.closure_voter import ClosureVoter
from .voter.traceable_voter import TraceableVoter
from .voter.vote import Vote

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .strategy.access_decision_strategy_interface import AccessDecisionStrategyInterface
    from .voter.access import Access
    from .voter.voter_interface import VoterInterface

__all__ = ["AccessDecisionManager"]

#: A cap on how many distinct ``(voter, attribute)`` applicability answers are
#: remembered. Static route attributes never approach it; a public entry point
#: that decides on caller-supplied strings could otherwise grow the cache
#: without bound, so the least-recently-used entry is dropped once it is reached.
_MAX_ATTRIBUTE_CACHE: Final = 4096

#: A cap on how many distinct ``(voter, subject type)`` applicability answers
#: are remembered. Bounded for the same reason as ``_MAX_ATTRIBUTE_CACHE``: a
#: public entry point deciding on caller-supplied subjects could otherwise grow
#: this cache without bound, so the least-recently-used entry is dropped once
#: it is reached.
_MAX_TYPE_CACHE: Final = 4096

#: The decisions in progress on the current task, innermost last. A voter that
#: asks a nested question reuses the decision on top, so its votes are gathered
#: into the one already being made rather than a fresh one.
_decision_stack: ContextVar[tuple[AccessDecision, ...]] = ContextVar(
    "xtr_security_access_decision_stack",
    default=(),
)


@final
class AccessDecisionManager(AccessDecisionManagerInterface):
    """Runs the voters for one attribute and reduces their votes with a strategy.

    Deciding is on exactly one attribute at a time: a rule or a call asking for
    several at once is refused, so that "granted" never quietly means "granted
    one of these". The voters are asked in order; a voter that has declared,
    through
    :class:`~xtr_security_core.authorization.voter.cacheable_voter_interface.CacheableVoterInterface`,
    that it never votes on this attribute or this subject type is skipped, and
    that applicability is remembered so the next decision does not ask again.

    A decision made by a voter while it votes — a closure asking a nested
    question — joins the decision already in progress, so every vote lands in
    one record.
    """

    __slots__ = ("_attribute_cache", "_strategy", "_type_cache", "_voters")

    def __init__(
        self,
        voters: Sequence[VoterInterface] = (),
        strategy: AccessDecisionStrategyInterface | None = None,
    ) -> None:
        """Record the voters and the strategy, and bind any closure voters."""
        self._voters: tuple[VoterInterface, ...] = tuple(voters)
        self._strategy: AccessDecisionStrategyInterface = (
            strategy if strategy is not None else AffirmativeStrategy()
        )
        self._attribute_cache: OrderedDict[tuple[int, str], bool] = OrderedDict()
        self._type_cache: OrderedDict[tuple[int, str], bool] = OrderedDict()
        for voter in self._voters:
            underlying = _unwrap(voter)
            if isinstance(underlying, ClosureVoter):
                underlying.bind_manager(self)

    @override
    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Decide whether ``token`` may have the one attribute over ``subject``."""
        attribute_list = list(attributes)
        if len(attribute_list) != 1:
            raise InvalidArgumentError(
                f"Deciding on exactly one attribute at a time is required; got {attribute_list!r}.",
            )
        attribute = attribute_list[0]
        stack = _decision_stack.get()
        owns_record = True
        if access_decision is None:
            if stack:
                access_decision = stack[-1]
                owns_record = False
            else:
                access_decision = AccessDecision(strategy=type(self._strategy).__name__)
        elif access_decision.strategy is None:
            access_decision.strategy = type(self._strategy).__name__
        reset_token = _decision_stack.set((*stack, access_decision))
        try:
            results = self._collect(token, attribute, attribute_list, subject, access_decision)
            try:
                granted = await self._strategy.decide(results, access_decision)
            finally:
                await results.aclose()
            if owns_record:
                access_decision.is_granted = granted
            return granted
        finally:
            _decision_stack.reset(reset_token)

    async def _collect(
        self,
        token: TokenInterface,
        attribute: object,
        attribute_list: Sequence[object],
        subject: object,
        access_decision: AccessDecision,
    ) -> AsyncGenerator[Access, None]:
        """Yield each applicable voter's answer, running it only when pulled."""
        for index, voter in enumerate(self._voters):
            if not self._supports(index, voter, attribute, subject):
                continue
            vote = Vote(voter=_unwrap(voter))
            result = await voter.vote(token, subject, attribute_list, vote)
            vote.result = result
            access_decision.votes.append(vote)
            yield result

    def _supports(
        self, index: int, voter: VoterInterface, attribute: object, subject: object
    ) -> bool:
        """Tell whether ``voter`` might vote on ``attribute`` over ``subject``."""
        if not isinstance(voter, CacheableVoterInterface):
            return True
        if not isinstance(attribute, str):
            return True
        attribute_key = (index, attribute)
        supported_attribute = self._attribute_cache.get(attribute_key)
        if supported_attribute is None:
            supported_attribute = voter.supports_attribute(attribute)
            if len(self._attribute_cache) >= _MAX_ATTRIBUTE_CACHE:
                _ = self._attribute_cache.popitem(last=False)
            self._attribute_cache[attribute_key] = supported_attribute
        else:
            self._attribute_cache.move_to_end(attribute_key)
        if not supported_attribute:
            return False
        type_name = _type_name(subject)
        type_key = (index, type_name)
        supported_type = self._type_cache.get(type_key)
        if supported_type is None:
            supported_type = voter.supports_type(type_name)
            if len(self._type_cache) >= _MAX_TYPE_CACHE:
                _ = self._type_cache.popitem(last=False)
            self._type_cache[type_key] = supported_type
        else:
            self._type_cache.move_to_end(type_key)
        return supported_type


def _type_name(subject: object) -> str:
    """Name the type of ``subject`` for a cacheable voter's ``supports_type``."""
    if subject is None:
        return "null"
    if isinstance(subject, bool):
        return "bool"
    if isinstance(subject, (list, tuple, dict, set, frozenset)):
        return "array"
    scalars: tuple[tuple[type, str], ...] = ((int, "int"), (float, "float"), (str, "string"))
    for scalar_type, name in scalars:
        if isinstance(subject, scalar_type):
            return name
    subject_type = type(subject)
    return f"{subject_type.__module__}.{subject_type.__qualname__}"


def _unwrap(voter: VoterInterface) -> VoterInterface:
    """Return the voter behind any layers of tracing decoration."""
    while isinstance(voter, TraceableVoter):
        voter = voter.get_decorated_voter()
    return voter
