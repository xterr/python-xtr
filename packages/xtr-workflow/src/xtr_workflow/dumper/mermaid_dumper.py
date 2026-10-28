"""Dumps a workflow or a state machine as a Mermaid flowchart."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_workflow.exception import InvalidArgumentError

from ._escaping import text_of
from .dumper_interface import DumperInterface

if TYPE_CHECKING:
    from xtr_workflow.arc import Arc
    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking

__all__ = ["MermaidDumper"]


@dataclass(frozen=True, slots=True)
class _TransitionDrawing:
    """What drawing one transition needs: its node, its label, its metadata, the places' nodes."""

    node_name: str
    label: str
    metadata: Mapping[str, object]
    place_node_names: Mapping[str, str]


@final
class MermaidDumper(DumperInterface):
    """Dumps a workflow or a state machine as a Mermaid flowchart.

    Places are numbered nodes, so a place may be named after a word Mermaid
    reserves; an initial place is drawn rounder. A workflow draws each
    transition as a node of its own, linked to the places it leaves and
    enters; a state machine draws it as a labelled link between them. Reads
    no option.

    A ``label`` entry replaces the name of a place or a transition, a
    ``bg_color`` entry fills it, and a transition's ``color`` entry colours
    its links. A marked place is drawn thicker, with its tokens counted when
    it holds more than one.
    """

    __slots__: tuple[str, ...] = ("_direction", "_link_count", "_transition_type")

    DIRECTION_TOP_TO_BOTTOM: Final = "TB"
    DIRECTION_TOP_DOWN: Final = "TD"
    DIRECTION_BOTTOM_TO_TOP: Final = "BT"
    DIRECTION_RIGHT_TO_LEFT: Final = "RL"
    DIRECTION_LEFT_TO_RIGHT: Final = "LR"

    _VALID_DIRECTIONS: Final = (
        DIRECTION_TOP_TO_BOTTOM,
        DIRECTION_TOP_DOWN,
        DIRECTION_BOTTOM_TO_TOP,
        DIRECTION_RIGHT_TO_LEFT,
        DIRECTION_LEFT_TO_RIGHT,
    )

    TRANSITION_TYPE_STATEMACHINE: Final = "statemachine"
    """Transitions drawn as labelled links, for a state machine."""

    TRANSITION_TYPE_WORKFLOW: Final = "workflow"
    """Transitions drawn as nodes of their own, for a workflow."""

    _VALID_TRANSITION_TYPES: Final = (TRANSITION_TYPE_STATEMACHINE, TRANSITION_TYPE_WORKFLOW)

    _transition_type: str
    _direction: str
    # Mermaid styles a link by its position among all links, which a
    # transition's position cannot tell once links are shared; so they are counted.
    _link_count: int

    def __init__(self, transition_type: str, direction: str = DIRECTION_LEFT_TO_RIGHT) -> None:
        """Draw transitions as ``transition_type`` says, the chart flowing in ``direction``.

        Args:
            transition_type: :attr:`TRANSITION_TYPE_STATEMACHINE` or
                :attr:`TRANSITION_TYPE_WORKFLOW`.
            direction: One of the ``DIRECTION_*`` constants.

        Raises:
            InvalidArgumentError: If either is not one of those.
        """
        self.validate_direction(direction)
        self._validate_transition_type(transition_type)
        self._transition_type = transition_type
        self._direction = direction
        self._link_count = 0

    @override
    def dump(
        self,
        definition: Definition,
        marking: Marking | None = None,
        options: Mapping[str, object] | None = None,
    ) -> str:
        """Return the Mermaid source of ``definition``, ``marking`` highlighted."""
        self._link_count = 0
        store = definition.get_metadata_store()
        initial_places = definition.get_initial_places()
        output = [f"graph {self._direction}"]
        place_node_names: dict[str, str] = {}

        for place_id, place in enumerate(definition.get_places()):
            metadata = store.get_place_metadata(place)
            node_name = f"place{place_id}"
            label = text_of(metadata["label"]) if "label" in metadata else place
            token_count = 0 if marking is None else marking.get_token_count(place)
            if token_count > 1:
                label += f" ({token_count})"
            shape = "([{}])" if place in initial_places else "(({}))"
            output.append(node_name + shape.format(self._escape(label)))
            style = self._style_node(
                metadata, node_name, marking is not None and marking.has(place)
            )
            if style:
                output.append(style)
            place_node_names[place] = node_name

        for transition_id, transition in enumerate(definition.get_transitions()):
            metadata = store.get_transition_metadata(transition)
            label = text_of(metadata["label"]) if "label" in metadata else transition.get_name()
            drawing = _TransitionDrawing(
                f"transition{transition_id}", label, metadata, place_node_names
            )
            for from_arc in transition.get_froms(as_arc=True):
                for to_arc in transition.get_tos(as_arc=True):
                    if self._transition_type == self.TRANSITION_TYPE_STATEMACHINE:
                        lines = self._style_state_machine_transition(from_arc, to_arc, drawing)
                    else:
                        lines = self._style_workflow_transition(from_arc, to_arc, drawing)
                    self._append_new_lines(output, lines)

        return "\n".join(output)

    def validate_direction(self, direction: str) -> None:
        """Refuse a direction Mermaid does not know.

        Raises:
            InvalidArgumentError: If ``direction`` is not one of the ``DIRECTION_*`` constants.
        """
        if direction not in self._VALID_DIRECTIONS:
            raise InvalidArgumentError(
                f'Direction "{direction}" is not valid, '
                f'valid directions are: "{", ".join(self._VALID_DIRECTIONS)}".'
            )

    def _validate_transition_type(self, transition_type: str) -> None:
        if transition_type not in self._VALID_TRANSITION_TYPES:
            raise InvalidArgumentError(
                f'Transition type "{transition_type}" is not valid, '
                f'valid types are: "{", ".join(self._VALID_TRANSITION_TYPES)}".'
            )

    def _append_new_lines(self, output: list[str], lines: list[str]) -> None:
        """Append each of ``lines`` not drawn yet; a link drawn already is not counted again."""
        for line in lines:
            if line in output:
                if line.find("-->") > 0:
                    self._link_count -= 1
                continue
            output.append(line)

    def _style_node(
        self, metadata: Mapping[str, object], node_name: str, has_marking: bool = False
    ) -> str:
        """Return the style line of a node, empty when it has no style."""
        node_styles: list[str] = []
        if "bg_color" in metadata:
            node_styles.append(f"fill:{text_of(metadata['bg_color'])}")
        if has_marking:
            node_styles.append("stroke-width:4px")
        return f"style {node_name} {','.join(node_styles)}" if node_styles else ""

    def _escape(self, label: str) -> str:
        """Return ``label`` quoted, the characters that would end it written as Mermaid entities."""
        # "#" goes first, so the entity written for a quote is not escaped again.
        return '"' + label.replace("#", "#35;").replace('"', "#quot;") + '"'

    def _style_state_machine_transition(
        self, from_arc: Arc, to_arc: Arc, drawing: _TransitionDrawing
    ) -> list[str]:
        """Return the labelled link a state machine draws between two places."""
        source = drawing.place_node_names[from_arc.place]
        target = drawing.place_node_names[to_arc.place]
        label = self._escape(drawing.label).replace("\n", " ")
        lines = [f"{source}-->|{label}|{target}"]
        self._add_link(lines, drawing.metadata)
        return lines

    def _style_workflow_transition(
        self, from_arc: Arc, to_arc: Arc, drawing: _TransitionDrawing
    ) -> list[str]:
        """Return the node a workflow draws for a transition and its links to two places."""
        node_name = drawing.node_name
        lines = [f"{node_name}[{self._escape(drawing.label)}]"]
        node_style = self._style_node(drawing.metadata, node_name)
        if node_style:
            lines.append(node_style)
        lines.append(
            self._link(drawing.place_node_names[from_arc.place], from_arc.weight, node_name)
        )
        self._add_link(lines, drawing.metadata)
        lines.append(self._link(node_name, to_arc.weight, drawing.place_node_names[to_arc.place]))
        self._add_link(lines, drawing.metadata)
        return lines

    def _link(self, source: str, weight: int, target: str) -> str:
        """Return a link, labelled with its weight when it moves more than one token."""
        return f"{source}-->|{weight}|{target}" if weight > 1 else f"{source}-->{target}"

    def _add_link(self, lines: list[str], metadata: Mapping[str, object]) -> None:
        """Count the link just drawn, styled with the transition's colour when it has one."""
        if "color" in metadata:
            lines.append(f"linkStyle {self._link_count} stroke:{text_of(metadata['color'])}")
        self._link_count += 1
