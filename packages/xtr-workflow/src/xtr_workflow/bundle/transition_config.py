"""Configuration of one transition of a configured workflow."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, TypeAlias, cast, final

from xtr_workflow.arc import Arc
from xtr_workflow.event_listener.guard_context import GuardContext
from xtr_workflow.exception import InvalidArgumentError

from .arc_config import ArcConfig

__all__ = ["TransitionConfig"]

_Arc: TypeAlias = str | Enum | Arc | ArcConfig
_Arcs: TypeAlias = _Arc | Sequence[_Arc]

# The default the typed signature below shows; the dataclass builds its own.
_NO_METADATA: Final[Mapping[str, object]] = MappingProxyType({})


@final
@dataclass(frozen=True, slots=True)
class TransitionConfig:
    """A transition of a configured workflow.

    The places it leaves and enters are given as arcs, each written the
    shortest way that says it: a place's name, a member of a string enum,
    an :class:`~xtr_workflow.Arc` or an :class:`ArcConfig` to weigh it — on
    its own or in a sequence::

        TransitionConfig("publish", froms="draft", tos=Status.PUBLISHED)
        TransitionConfig("merge", froms=(ArcConfig("done", 2), "extra"), tos="archived")

    Attributes:
        name: The name of the transition. A transition keyed by its name in
            :attr:`WorkflowDefinitionConfig.transitions` may leave it empty,
            to be named by its key.
        froms: The arcs from the places the transition leaves.
        tos: The arcs to the places the transition enters.
        guard: Called with the guard context — the subject, the security
            token and what to check it with; the transition is enabled only
            when it returns true, or an awaitable resolving to true.
        weight: Checked to be at least 1, and read by nothing: only the
            weights of the arcs count. It is kept so a configuration setting
            it still reads.
        metadata: The metadata of the transition, its ``description``
            included.
    """

    name: str = ""
    froms: tuple[ArcConfig, ...] = ()
    tos: tuple[ArcConfig, ...] = ()
    guard: Callable[[GuardContext], bool | Awaitable[bool]] | None = None
    weight: int = 1
    metadata: Mapping[str, object] = field(default_factory=dict[str, object])

    if TYPE_CHECKING:
        # The arcs may be given in every shorthand above, read into
        # ``ArcConfig`` tuples by ``__post_init__``; the attributes always
        # hold the tuples.
        def __init__(  # noqa: PLR0913 — one parameter per option of a transition.
            self,
            name: str = "",
            froms: _Arcs = (),
            tos: _Arcs = (),
            *,
            guard: Callable[[GuardContext], bool | Awaitable[bool]] | None = None,
            weight: int = 1,
            metadata: Mapping[str, object] = _NO_METADATA,
        ) -> None:
            """Name the transition and the places it moves tokens between."""

    def __post_init__(self) -> None:
        """Read the arcs into :class:`ArcConfig` tuples, and check the weight.

        Raises:
            InvalidArgumentError: If an arc names no place, or the weight is
                below 1.
        """
        object.__setattr__(self, "froms", _arcs(self.froms, "froms"))
        object.__setattr__(self, "tos", _arcs(self.tos, "tos"))
        if self.weight < 1:
            raise InvalidArgumentError("The weight must be greater than 0.")


def _arcs(arcs: _Arcs, option: str) -> tuple[ArcConfig, ...]:
    """Return ``arcs`` — one arc or several, however written — as :class:`ArcConfig` instances.

    Raises:
        InvalidArgumentError: If an arc is neither a place's name, an enum
            member, an :class:`Arc` nor an :class:`ArcConfig`.
    """
    # Typed loosely: configuration is written by hand, its annotations not enforced at runtime.
    given = cast(
        "Sequence[object]", (arcs,) if isinstance(arcs, str | Enum | Arc | ArcConfig) else arcs
    )
    read: list[ArcConfig] = []
    for arc in given:
        match arc:
            case ArcConfig():
                read.append(arc)
            case Arc(place=place, weight=weight):
                read.append(ArcConfig(place, weight))
            case str() | Enum():
                read.append(ArcConfig(arc))
            case _:
                raise InvalidArgumentError(
                    f'The "{option}" arcs must be a list of strings, enum members, arcs or arc '
                    "configurations in workflow configuration."
                )
    return tuple(read)
