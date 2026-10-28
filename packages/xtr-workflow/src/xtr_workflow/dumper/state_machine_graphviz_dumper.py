"""Dumps a state machine as a Graphviz graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from ._graphviz_nodes import PlaceEdge
from ._options import replace_recursive
from .graphviz_dumper import GraphvizDumper

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking

__all__ = ["StateMachineGraphvizDumper"]


@final
class StateMachineGraphvizDumper(GraphvizDumper):
    """Dumps a state machine as a Graphviz graph: places as circles, transitions as labelled edges.

    A state machine moves a subject from one place to one place, so a
    transition reads best as an arrow between them rather than as a box of
    its own. Reads the same options as :class:`GraphvizDumper`, but lists no
    listeners, having no transition node to list them on. A ``color`` entry
    colours a transition's label, an ``arrow_color`` entry its arrow.
    """

    __slots__: tuple[str, ...] = ()

    @override
    def dump(
        self,
        definition: Definition,
        marking: Marking | None = None,
        options: Mapping[str, object] | None = None,
    ) -> str:
        """Return the Graphviz source of ``definition``, ``marking`` highlighted."""
        given = options or {}
        with_metadata = bool(given.get("with-metadata", False))

        places = self._find_places(definition, with_metadata, marking)
        edges = self._find_place_edges(definition)
        merged = replace_recursive(self._DEFAULT_OPTIONS, given)
        label = self._format_label(definition, with_metadata, merged)

        return (
            self._start_dot(merged, label)
            + self._add_places(places)
            + self._add_place_edges(edges)
            + self._end_dot()
        )

    def _find_place_edges(self, definition: Definition) -> dict[str, list[PlaceEdge]]:
        """Return an edge per pair of places a transition moves between, by the place it leaves.

        Places come in the order a transition first leaves them, and so does
        the drawing.
        """
        store = definition.get_metadata_store()
        edges: dict[str, list[PlaceEdge]] = {}
        for transition in definition.get_transitions():
            attributes: dict[str, object] = {}
            label = store.get_metadata("label", transition)
            label_color = store.get_metadata("color", transition)
            if label_color is not None:
                attributes["fontcolor"] = label_color
            arrow_color = store.get_metadata("arrow_color", transition)
            if arrow_color is not None:
                attributes["color"] = arrow_color
            name = transition.get_name() if label is None else label
            for from_arc in transition.get_froms(as_arc=True):
                edges.setdefault(from_arc.place, []).extend(
                    PlaceEdge(name, to_arc.place, attributes)
                    for to_arc in transition.get_tos(as_arc=True)
                )
        return edges

    def _add_place_edges(self, edges: Mapping[str, list[PlaceEdge]]) -> str:
        """Return each edge, labelled with the transition's name."""
        code = ""
        for place, place_edges in edges.items():
            for edge in place_edges:
                attributes = self._add_attributes(edge.attributes)
                code += (
                    f"  place_{self._dotize(place)} -> place_{self._dotize(edge.to)} "
                    f'[label="{self._escape(edge.name)}" style="solid"{attributes}];\n'
                )
        return code
