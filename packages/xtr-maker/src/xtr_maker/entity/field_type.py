"""FieldType: the kinds of column ``make:entity`` writes, and the one a name suggests."""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["FieldType"]


@unique
class FieldType(StrEnum):
    """A column's kind, named as it is typed at the prompt and in ``--field``.

    Each one is a Python type on the attribute and a column type in the
    database: ``string`` is ``str`` in a ``String(length)``, ``datetime`` a
    timezone-aware ``datetime`` in a ``DateTimeUTC`` column, ``json`` a
    ``dict[str, object]`` in a ``JsonB`` one.
    """

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    BIG_INTEGER = "big_integer"
    SMALL_INTEGER = "small_integer"
    BOOLEAN = "boolean"
    FLOAT = "float"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    TIME = "time"
    JSON = "json"
    UUID = "uuid"
    ENUM = "enum"
    BINARY = "binary"

    @classmethod
    def guess(cls, name: str) -> FieldType:
        """Return the kind a property called ``name`` most likely holds.

        ``published_at`` is a ``datetime``, ``author_id`` a ``uuid``,
        ``is_active`` and ``has_stock`` are ``boolean``; anything else is a
        ``string``. It is only the default offered: the answer decides.
        """
        if name.endswith("_at"):
            return cls.DATETIME
        if name.endswith("_id"):
            return cls.UUID
        if name.startswith(("is_", "has_")):
            return cls.BOOLEAN
        return cls.STRING
