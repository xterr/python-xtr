"""RelationKind: how many rows of one entity relate to how many of another."""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["RelationKind"]


@unique
class RelationKind(StrEnum):
    """A relation, read from the entity it is added to.

    ``many_to_one``: many books, one author — the book holds ``author_id``.
    ``one_to_many``: the same relation added to the author — the book still
    holds the key. ``one_to_one``: a key that is unique. ``many_to_many``: an
    association table holds a key to each side.
    """

    MANY_TO_ONE = "many_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"
    ONE_TO_ONE = "one_to_one"

    @property
    def holds_key(self) -> bool:
        """Whether the entity the relation is added to holds the foreign key."""
        return self in {RelationKind.MANY_TO_ONE, RelationKind.ONE_TO_ONE}

    @property
    def is_collection(self) -> bool:
        """Whether the property added reaches a list of the other entity."""
        return self in {RelationKind.ONE_TO_MANY, RelationKind.MANY_TO_MANY}

    @property
    def is_inverse_collection(self) -> bool:
        """Whether the property added to the other entity reaches a list."""
        return self in {RelationKind.MANY_TO_ONE, RelationKind.MANY_TO_MANY}

    @property
    def requires_inverse(self) -> bool:
        """Whether the other entity must get a property: it holds the key the relation needs."""
        return self is RelationKind.ONE_TO_MANY

    @property
    def may_be_null(self) -> bool:
        """Whether the relation has a foreign key that can be left empty."""
        return self is not RelationKind.MANY_TO_MANY
