"""Dumps a workflow or a state machine as a PlantUML diagram."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override

from xtr_workflow.exception import InvalidArgumentError

from ._escaping import text_of
from ._options import replace_recursive
from .dumper_interface import DumperInterface

if TYPE_CHECKING:
    from xtr_workflow.definition import Definition
    from xtr_workflow.marking import Marking
    from xtr_workflow.metadata import MetadataStoreInterface
    from xtr_workflow.transition import Transition

__all__ = ["PlantUmlDumper"]

_INITIAL: Final = "<<initial>>"
_MARKED: Final = "<<marked>>"


@final
class PlantUmlDumper(DumperInterface):
    """Dumps a workflow or a state machine as a PlantUML diagram.

    Render the dump with PlantUML (https://plantuml.com/)::

        java -jar plantuml.jar -p < workflow.puml > workflow.png

    A workflow draws each transition as a square of its own, linked to the
    places it leaves and enters; a state machine draws it as a labelled arrow
    between them. Options read, all optional: ``title`` and ``name``, each a
    title line, and ``skinparams``, laid over :attr:`DEFAULT_OPTIONS`.

    A place's ``bg_color`` entry fills it and its ``description`` entry shows
    under it, a line per non-empty line. A transition's ``label`` entry
    replaces its name, its ``color`` entry colours that, and its
    ``arrow_color`` entry colours its arrows.
    """

    __slots__: tuple[str, ...] = ("_transition_type",)

    STATEMACHINE_TRANSITION: Final = "arrow"
    """Transitions drawn as labelled arrows, for a state machine."""

    WORKFLOW_TRANSITION: Final = "square"
    """Transitions drawn as squares of their own, for a workflow."""

    TRANSITION_TYPES: Final = (STATEMACHINE_TRANSITION, WORKFLOW_TRANSITION)

    DEFAULT_OPTIONS: Final[Mapping[str, object]] = {
        "skinparams": {
            "titleBorderRoundCorner": 15,
            "titleBorderThickness": 2,
            "state": {
                f"BackgroundColor{_INITIAL}": "#87b741",
                f"BackgroundColor{_MARKED}": "#3887C6",
                "BorderColor": "#3887C6",
                f"BorderColor{_MARKED}": "Black",
                f"FontColor{_MARKED}": "White",
            },
            "agent": {
                "BackgroundColor": "#ffffff",
                "BorderColor": "#3887C6",
            },
        },
    }

    _transition_type: str

    def __init__(self, transition_type: str) -> None:
        """Draw transitions as ``transition_type`` says.

        Args:
            transition_type: :attr:`STATEMACHINE_TRANSITION` or :attr:`WORKFLOW_TRANSITION`.

        Raises:
            InvalidArgumentError: If ``transition_type`` is neither.
        """
        if transition_type not in self.TRANSITION_TYPES:
            raise InvalidArgumentError(f"Transition type '{transition_type}' does not exist.")
        self._transition_type = transition_type

    @override
    def dump(
        self,
        definition: Definition,
        marking: Marking | None = None,
        options: Mapping[str, object] | None = None,
    ) -> str:
        """Return the PlantUML source of ``definition``, ``marking`` highlighted."""
        merged = replace_recursive(self.DEFAULT_OPTIONS, options or {})
        code = self._initialize(merged, definition)
        code.extend(
            self._get_state(place, definition, marking) for place in definition.get_places()
        )
        if self._is_workflow_transition_type():
            code.extend(f"agent {self._escape(t.get_name())}" for t in definition.get_transitions())
        for transition in definition.get_transitions():
            for line in self._transition_lines(transition, definition.get_metadata_store()):
                # A workflow draws a transition's square once, however many places it links.
                if not self._is_workflow_transition_type() or line not in code:
                    code.append(line)

        return "@startuml\nallow_mixing\n" + "\n".join(code) + "\n@enduml"

    def _is_workflow_transition_type(self) -> bool:
        return self._transition_type == self.WORKFLOW_TRANSITION

    def _initialize(self, options: Mapping[str, object], definition: Definition) -> list[str]:
        """Return the title lines and the skin parameters, a fill style for each coloured place."""
        store = definition.get_metadata_store()
        code: list[str] = []
        for title_key in ("title", "name"):
            title = options.get(title_key)
            if title is not None:
                code.append(f"title {text_of(title)}")

        skinparams = options.get("skinparams")
        for place in definition.get_places():
            background_color = store.get_metadata("bg_color", place)
            if background_color is not None and isinstance(skinparams, dict):
                state = cast("dict[str, object]", skinparams).setdefault("state", {})
                if isinstance(state, dict):
                    key = f"BackgroundColor<<{self._get_color_id(text_of(background_color))}>>"
                    cast("dict[str, object]", state)[key] = background_color

        if not isinstance(skinparams, Mapping):
            return code
        for key, value in cast("Mapping[str, object]", skinparams).items():
            if not self._is_workflow_transition_type() and key == "agent":
                continue
            if not isinstance(value, Mapping):
                code.append(f"skinparam {key} {text_of(value)}")
                continue
            code.append(f"skinparam {key} {{")
            code.extend(
                f"    {name} {text_of(item)}"
                for name, item in cast("Mapping[str, object]", value).items()
            )
            code.append("}")
        return code

    def _transition_lines(self, transition: Transition, store: MetadataStoreInterface) -> list[str]:
        """Return the lines linking ``transition`` to each pair of places it moves between."""
        transition_escaped = self._escape(transition.get_name())
        with_style = self._get_transition_escaped_with_style(store, transition, transition_escaped)
        arrow_color = store.get_metadata("arrow_color", transition)
        color = "" if arrow_color is None else self._get_transition_color(text_of(arrow_color))
        # A workflow's square shows the label only when the label is styled.
        label = f": {with_style}" if with_style != transition_escaped else ""

        lines: list[str] = []
        for from_arc in transition.get_froms(as_arc=True):
            from_escaped = self._escape(from_arc.place)
            for to_arc in transition.get_tos(as_arc=True):
                to_escaped = self._escape(to_arc.place)
                if self._is_workflow_transition_type():
                    lines.append(f"{from_escaped} -{color}-> {transition_escaped}{label}")
                    lines.append(f"{transition_escaped} -{color}-> {to_escaped}{label}")
                else:
                    lines.append(f"{from_escaped} -{color}-> {to_escaped}: {with_style}")
        return lines

    def _escape(self, text: str) -> str:
        """Return ``text`` quoted; a double quote cannot be escaped, so it is dropped."""
        return '"' + text.replace('"', "") + '"'

    def _get_state(self, place: str, definition: Definition, marking: Marking | None) -> str:
        """Return the state of ``place``, its styles, and a line per line of its description."""
        store = definition.get_metadata_store()
        place_escaped = self._escape(place).replace("\n", " ")
        output = f"state {place_escaped}"
        if place in definition.get_initial_places():
            output += f" {_INITIAL}"
        if marking is not None and marking.has(place):
            output += f" {_MARKED}"

        background_color = store.get_metadata("bg_color", place)
        if background_color is not None:
            output += f" <<{self._get_color_id(text_of(background_color))}>>"

        description = store.get_metadata("description", place)
        if description is not None:
            for line in text_of(description).split("\n"):
                # An empty line, and one reading "0", count as no line.
                if line not in {"", "0"}:
                    output += f"\n{place_escaped} : {line}"
        return output

    def _get_transition_escaped_with_style(
        self, store: MetadataStoreInterface, transition: Transition, to: str
    ) -> str:
        """Return the transition's label, or ``to``, coloured and quoted, on one line.

        A line break becomes a backslash and an ``n``, which PlantUML breaks the label at.
        """
        label = store.get_metadata("label", transition)
        # PlantUML breaks a label at a literal "\n".
        text = (to if label is None else text_of(label)).replace("\n", "\\n")

        color = store.get_metadata("color", transition)
        if color is not None:
            # Close and reopen the font at each break, so every line is coloured.
            color_text = text_of(color)
            text = text.replace("\\n", f"</font>\\n<font color={color_text}>")
            text = f"<font color={color_text}>{text}</font>"

        return self._escape(text)

    def _get_transition_color(self, color: str) -> str:
        """Return ``color`` as an arrow style; PlantUML wants it after a ``#``."""
        return f"[{color if color.startswith('#') else '#' + color}]"

    def _get_color_id(self, color: str) -> str:
        """Return ``color`` without its leading ``#``, so it can name a style."""
        return color.lstrip("#")
