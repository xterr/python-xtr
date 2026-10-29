"""EntityInterviewer: the questions ``make:entity`` asks for each field or relation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_maker.exception import InvalidArgumentError

from .entity_field import EntityField
from .entity_relation import EntityRelation
from .field_type import FieldType
from .property_name import PropertyName
from .relation_kind import RelationKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_console import ConsoleStyle

__all__ = ["EntityInterviewer"]

_LIST: Final = "?"
_RELATION: Final = "relation"
_NONE: Final = "none"


@final
class EntityInterviewer:
    """Asks for one property at a time: its name, its type, then what that type needs.

    An empty name ends the questions. The type offered is the one the name
    suggests; ``?`` lists every type, and ``relation`` — or a relation kind
    typed directly — asks for a relation instead of a column.
    """

    __slots__ = ("_io", "_owner")

    def __init__(self, io: ConsoleStyle, owner: str) -> None:
        """Ask through ``io`` for properties of the entity class ``owner``.

        Args:
            io: Where the questions are asked.
            owner: The entity's class name, which the default inverse names follow.
        """
        self._io = io
        self._owner = owner

    def next_member(self, taken: Callable[[str], bool]) -> EntityField | EntityRelation | None:
        """Ask for the next property; ``None`` once the name is left empty.

        Args:
            taken: Whether the entity already has a property of a given name.

        Raises:
            InvalidArgumentError: When an answer cannot be used; the caller
                reports it and asks for the next property.
        """
        typed = self._io.ask("New property name (press [cyan]<return>[/] to stop adding fields)")
        if not typed.strip():
            return None
        name = PropertyName.check(typed)
        if taken(name):
            raise InvalidArgumentError(f"{self._owner} already has a property {name!r}.")
        kind = self._type(name)
        if isinstance(kind, RelationKind):
            return self._relation(name, kind)
        return self._field(name, kind)

    def _type(self, name: str) -> FieldType | RelationKind:
        question = "Field type (enter [cyan]?[/] to see all types)"
        answer = self._io.ask(question, FieldType.guess(name)).strip().lower()
        while answer == _LIST:
            self._io.listing([*FieldType, f"{_RELATION} — or one of {', '.join(RelationKind)}"])
            answer = self._io.ask(question, FieldType.guess(name)).strip().lower()
        if answer == _RELATION:
            kind = self._io.ask(
                "What type of relation", RelationKind.MANY_TO_ONE, choices=tuple(RelationKind)
            )
            return EntityRelation.kind_named(kind)
        if answer in tuple(RelationKind):
            return RelationKind(answer)
        try:
            return FieldType(answer)
        except ValueError:
            raise InvalidArgumentError(
                f"There is no field type {answer!r}; enter ? to see them all."
            ) from None

    def _field(self, name: str, kind: FieldType) -> EntityField:
        length, precision, scale = (
            EntityField.DEFAULT_LENGTH,
            EntityField.DEFAULT_PRECISION,
            EntityField.DEFAULT_SCALE,
        )
        enum_class = None
        match kind:
            case FieldType.STRING:
                length = self._number("Field length", length)
            case FieldType.DECIMAL:
                precision = self._number("Precision (how many digits in all)", precision)
                scale = self._number("Scale (how many digits after the point)", scale)
            case FieldType.ENUM:
                enum_class = self._io.ask(
                    "Enum class, dotted (such as [cyan]app.entity.enum.Status[/])"
                ).strip()
                _ = EntityField.enum_type(enum_class)
            case _:
                pass
        nullable = self._io.confirm("Can this field be null in the database (nullable)")
        return EntityField(name, kind, nullable, length, precision, scale, enum_class)

    def _relation(self, name: str, kind: RelationKind) -> EntityRelation:
        target = self._io.ask("Which entity does it relate to (such as [cyan]Author[/])").strip()
        if not target:
            raise InvalidArgumentError("Name the entity the relation reaches.")
        nullable = kind.may_be_null and self._io.confirm("Can its key be left empty (nullable)")
        default = EntityRelation.default_inverse(kind, self._owner)
        if kind.requires_inverse:
            question = f"The property on {target} that holds the key to {self._owner}"
        else:
            question = f"The property on {target} that reaches back ([cyan]{_NONE}[/] for none)"
        inverse = self._io.ask(question, default).strip()
        return EntityRelation(
            name, kind, target, nullable, None if inverse.lower() == _NONE else inverse
        )

    def _number(self, question: str, default: int) -> int:
        answer = self._io.ask(question, str(default)).strip()
        try:
            return int(answer)
        except ValueError:
            raise InvalidArgumentError(f"{answer!r} is not a whole number.") from None
