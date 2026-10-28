"""Dumps a workflow as a Graphviz graph."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, ClassVar, cast

from typing_extensions import override

from ._escaping import addslashes, escape_html, text_of
from ._graphviz_nodes import Edge, PlaceNode, TransitionNode
from ._options import mapping_at, replace_recursive
from .dumper_interface import DumperInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking

    from ._graphviz_nodes import Listeners

__all__ = ["GraphvizDumper"]


class GraphvizDumper(DumperInterface):
    """Dumps a workflow as a Graphviz graph: places as circles, transitions as boxes.

    Render the dump with the ``dot`` tool (https://graphviz.org/)::

        dot -Tpng workflow.dot > workflow.png

    Options read, all optional:

    * ``graph``, ``node``, ``edge``: Graphviz attributes laid over the default
      style of the whole graph, of its nodes and of its edges.
    * ``label``: the graph's title.
    * ``with-metadata``: list the metadata of the workflow, of each place and
      of each transition on the diagram.
    * ``listeners``: the listeners of each transition, under
      ``"transition__<number>"``, by event, each a mapping with a ``title``
      and, for a guard, its ``guardExpressions``; listed on the transition.

    Initial places are filled and marked places drawn red and double; a
    ``bg_color`` entry fills a place or a transition, a ``label`` entry
    replaces its name, a ``description`` entry shows in italics under it.
    """

    __slots__: tuple[str, ...] = ()

    # Every value is text, written as given.
    _DEFAULT_OPTIONS: ClassVar[Mapping[str, Mapping[str, str]]] = {
        "graph": {"ratio": "compress", "rankdir": "LR"},
        "node": {
            "fontsize": "9",
            "fontname": "Arial",
            "color": "#333333",
            "fillcolor": "lightblue",
            "fixedsize": "false",
            "width": "1",
        },
        "edge": {
            "fontsize": "9",
            "fontname": "Arial",
            "color": "#333333",
            "arrowhead": "normal",
            "arrowsize": "0.5",
        },
    }

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
        listeners = cast("Listeners", given.get("listeners") or {})

        places = self._find_places(definition, with_metadata, marking)
        transitions = self._find_transitions(definition, with_metadata, listeners)
        edges = self._find_edges(definition)
        merged = replace_recursive(self._DEFAULT_OPTIONS, given)
        label = self._format_label(definition, with_metadata, merged)

        return (
            self._start_dot(merged, label)
            + self._add_places(places)
            + self._add_transitions(transitions)
            + self._add_edges(edges)
            + self._end_dot()
        )

    def _find_places(
        self, definition: Definition, with_metadata: bool, marking: Marking | None
    ) -> dict[str, PlaceNode]:
        """Return how each place is drawn, by place name."""
        store = definition.get_metadata_store()
        initial_places = definition.get_initial_places()
        places: dict[str, PlaceNode] = {}
        for place in definition.get_places():
            attributes: dict[str, object] = {}
            if place in initial_places:
                attributes["style"] = "filled"
            if marking is not None and marking.has(place):
                attributes["color"] = "#FF0000"
                attributes["shape"] = "doublecircle"
            background_color = store.get_metadata("bg_color", place)
            if background_color is not None:
                attributes["style"] = "filled"
                attributes["fillcolor"] = background_color
            metadata = dict(store.get_place_metadata(place)) if with_metadata else {}
            label = store.get_metadata("label", place)
            if label is not None:
                # The label shows as the name, so it is not listed again.
                _ = metadata.pop("label", None)
            places[place] = PlaceNode(attributes, metadata, label)
        return places

    def _find_transitions(
        self, definition: Definition, with_metadata: bool, listeners: Listeners
    ) -> list[TransitionNode]:
        """Return how each transition is drawn, in order, its listeners listed with its metadata."""
        store = definition.get_metadata_store()
        transitions: list[TransitionNode] = []
        for number, transition in enumerate(definition.get_transitions()):
            attributes: dict[str, object] = {"shape": "box", "regular": True}
            background_color = store.get_metadata("bg_color", transition)
            if background_color is not None:
                attributes["style"] = "filled"
                attributes["fillcolor"] = background_color
            name = store.get_metadata("label", transition)
            metadata: dict[str, object] = {}
            if with_metadata:
                metadata = dict(store.get_transition_metadata(transition))
                _ = metadata.pop("label", None)
                _ = metadata.pop("bg_color", None)
            listener_number = 0
            for event_listeners in listeners.get(f"transition__{number}", {}).values():
                for details in event_listeners:
                    title = details["title"]
                    guard_expressions = details.get("guardExpressions")
                    if guard_expressions is not None:
                        expressions = cast("Sequence[object]", guard_expressions)
                        title = "Guard: " + " && ".join(text_of(item) for item in expressions)
                    metadata[f"Listener #{listener_number}"] = title
                    listener_number += 1
            transitions.append(
                TransitionNode(
                    attributes, transition.get_name() if name is None else name, metadata
                )
            )
        return transitions

    def _add_places(self, places: Mapping[str, PlaceNode]) -> str:
        """Return the node of each place."""
        code = ""
        for place_id, place in places.items():
            metadata = dict(place.metadata)
            _ = metadata.pop("bg_color", None)
            description = metadata.pop("description", None)
            escaped_label = self._label_of(
                place_id if place.label is None else place.label, metadata, description
            )
            code += (
                f"  place_{self._dotize(place_id)} [label={escaped_label}, shape=circle"
                f"{self._add_attributes(place.attributes)}];\n"
            )
        return code

    def _add_transitions(self, transitions: Sequence[TransitionNode]) -> str:
        """Return the box of each transition."""
        code = ""
        for number, transition in enumerate(transitions):
            metadata = dict(transition.metadata)
            description = metadata.pop("description", None)
            escaped_label = self._label_of(transition.name, metadata, description)
            code += (
                f"  transition_{self._dotize(str(number))} [label={escaped_label},"
                f"{self._add_attributes(transition.attributes)}];\n"
            )
        return code

    def _label_of(self, name: object, metadata: Mapping[str, object], description: object) -> str:
        """Return the markup label of a node: its name in bold, its metadata, its description."""
        description_label = "" if description is None else f"<BR/><I>{escape_html(description)}</I>"
        return f"<<B>{escape_html(name)}</B>{self._add_metadata(metadata)}{description_label}>"

    def _find_edges(self, definition: Definition) -> list[Edge]:
        """Return every arc of every transition, in order, those it leaves first."""
        edges: list[Edge] = []
        for number, transition in enumerate(definition.get_transitions()):
            edges.extend(
                Edge(arc.place, number, leaves_place=True, weight=arc.weight)
                for arc in transition.get_froms(as_arc=True)
            )
            edges.extend(
                Edge(arc.place, number, leaves_place=False, weight=arc.weight)
                for arc in transition.get_tos(as_arc=True)
            )
        return edges

    def _add_edges(self, edges: Sequence[Edge]) -> str:
        """Return each arc, labelled with its weight when it moves more than one token."""
        code = ""
        for edge in edges:
            place = f"place_{self._dotize(edge.place)}"
            transition = f"transition_{self._dotize(str(edge.transition_number))}"
            source, target = (place, transition) if edge.leaves_place else (transition, place)
            weight = f',label="{self._escape(edge.weight)}"' if edge.weight > 1 else ""
            code += f'  {source} -> {target} [style="solid"{weight}];\n'
        return code

    def _start_dot(self, options: Mapping[str, object], label: str) -> str:
        """Return the opening of the graph: its style, its title, the node and edge style."""
        title = f" label={label}" if label not in {'""', "<>"} else ""
        return (
            "digraph workflow {\n"
            f"  {self._add_options(mapping_at(options, 'graph'))}{title}\n"
            f"  node [{self._add_options(mapping_at(options, 'node'))}];\n"
            f"  edge [{self._add_options(mapping_at(options, 'edge'))}];\n\n"
        )

    def _end_dot(self) -> str:
        """Return the closing of the graph."""
        return "}\n"

    def _dotize(self, node_id: str) -> str:
        """Return a node name made of ``node_id``, safe whatever characters it holds."""
        return hashlib.sha1(node_id.encode(), usedforsecurity=False).hexdigest()

    def _escape(self, value: object) -> str:
        """Return ``value`` fit for a quoted attribute; a flag reads ``1`` or ``0``."""
        if isinstance(value, bool):
            return "1" if value else "0"
        return addslashes(text_of(value))

    def _add_attributes(self, attributes: Mapping[str, object]) -> str:
        """Return ``attributes`` as quoted Graphviz attributes, after a space when there are any."""
        code = [f'{key}="{self._escape(value)}"' for key, value in attributes.items()]
        return " " + " ".join(code) if code else ""

    def _format_label(
        self, definition: Definition, with_metadata: bool, options: Mapping[str, object]
    ) -> str:
        """Return the graph's title, already escaped.

        Without metadata, the ``label`` option quoted, empty when unset. With
        it, the workflow's metadata and description, under the ``label``
        option in bold when set.
        """
        label = options.get("label")
        current_label = "" if label is None else label
        if not with_metadata:
            return f'"{self._escape(current_label)}"'

        workflow_metadata = dict(definition.get_metadata_store().get_workflow_metadata())
        _ = workflow_metadata.pop("bg_color", None)
        description = workflow_metadata.pop("description", None)
        description_label = "" if description is None else f"<I>{escape_html(description)}</I>"

        if current_label == "":
            metadata = self._add_metadata(workflow_metadata, line_break_first=False)
            separator = "<BR/>" if metadata and description_label else ""
            return f"<{metadata}{separator}{description_label}>"

        separator = "<BR/>" if description_label else ""
        return (
            f"<<B>{escape_html(current_label)}</B>{self._add_metadata(workflow_metadata)}"
            f"{separator}{description_label}>"
        )

    def _add_options(self, options: Mapping[str, object]) -> str:
        """Return ``options`` as quoted Graphviz attributes, written as given."""
        return " ".join(f'{key}="{text_of(value)}"' for key, value in options.items())

    def _add_metadata(self, metadata: Mapping[str, object], line_break_first: bool = True) -> str:
        """Return each entry as ``key: value``, after a line break unless first and told not to."""
        entries = [f"{escape_html(key)}: {escape_html(value)}" for key, value in metadata.items()]
        if line_break_first:
            return "".join(f"<BR/>{entry}" for entry in entries)
        return "<BR/>".join(entries)
