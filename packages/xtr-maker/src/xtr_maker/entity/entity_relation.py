"""EntityRelation: one relation ``make:entity`` adds, read from ``--relation`` or the answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

from xtr_maker.exception import InvalidArgumentError
from xtr_maker.name_converter import NameConverter

from .property_name import PropertyName
from .relation_kind import RelationKind

__all__ = ["EntityRelation"]

_NONE: Final = "none"
"""The inverse name that adds no property to the other entity."""


@final
@dataclass(frozen=True, slots=True)
class EntityRelation:
    """A relation from the entity being made to another, and back.

    Attributes:
        name: The property added to this entity.
        kind: How many of each side relate.
        target: The other entity, as typed: ``Author``, or ``catalog.Author``
            for one under ``entity/catalog/``.
        nullable: Whether the foreign key may be left empty.
        inverse: The property added to the other entity to reach back;
            ``None`` adds none.

    Raises:
        InvalidArgumentError: When a name cannot name an attribute, or the
            relation needs the inverse it was not given.
    """

    name: str
    kind: RelationKind
    target: str
    nullable: bool = False
    inverse: str | None = None

    def __post_init__(self) -> None:
        """Refuse names no attribute can have, and a relation missing the side holding its key."""
        _ = PropertyName.check(self.name)
        if self.inverse is not None:
            _ = PropertyName.check(self.inverse)
        elif self.kind.requires_inverse:
            raise InvalidArgumentError(
                f"A {self.kind} relation needs the property on {self.target} that holds"
                " its key: name the inverse."
            )
        if self.nullable and not self.kind.may_be_null:
            raise InvalidArgumentError(f"A {self.kind} relation has no key to leave empty.")

    @classmethod
    def parse(cls, typed: str, owner: str) -> EntityRelation:
        """Read ``name:kind:Target[?][,inverse=name|none]``, as ``--relation`` takes it.

        ``author:many_to_one:Author,inverse=books``; ``?`` after the target
        makes the key nullable. Left out, the inverse is the one
        :meth:`default_inverse` names for ``owner``, the entity being made;
        ``inverse=none`` adds none.

        Raises:
            InvalidArgumentError: When it does not read as a relation.
        """
        head, *options = (part.strip() for part in typed.split(","))
        parts = [part.strip() for part in head.split(":")]
        settings = {
            key.strip(): value.strip()
            for key, _, value in (option.partition("=") for option in options)
        }
        if len(parts) != 3 or not all(parts) or set(settings) - {"inverse"}:  # noqa: PLR2004 — name, kind, target.
            raise InvalidArgumentError(
                f"{typed!r} does not read as a relation: write name:kind:Target[?][,inverse=name],"
                " such as author:many_to_one:Author,inverse=books."
            )
        name, kind_typed, target = parts
        kind = cls.kind_named(kind_typed)
        nullable = target.endswith("?")
        target = target.removesuffix("?")
        inverse = settings.get("inverse", cls.default_inverse(kind, owner)).strip()
        return cls(name, kind, target, nullable, None if inverse.lower() == _NONE else inverse)

    @staticmethod
    def kind_named(typed: str) -> RelationKind:
        """Return the relation kind ``typed`` names.

        Raises:
            InvalidArgumentError: When it names none.
        """
        try:
            return RelationKind(typed.strip().lower())
        except ValueError:
            raise InvalidArgumentError(
                f"There is no relation kind {typed!r}; the kinds are {', '.join(RelationKind)}."
            ) from None

    @staticmethod
    def default_inverse(kind: RelationKind, owner: str) -> str:
        """Return the property ``owner``'s relation of ``kind`` gets on the other entity.

        The owner's name, snake-cased, in the plural when the other side
        reaches many of it: a book's ``many_to_one`` author reaches back with
        ``books``, an author's ``one_to_many`` books with ``author``.
        """
        snake = NameConverter.as_snake_case(owner)
        return NameConverter.pluralize(snake) if kind.is_inverse_collection else snake

    @property
    def key_name(self) -> str:
        """The foreign key column the side holding the key gets: ``author`` → ``author_id``."""
        return f"{self.name}_id"
