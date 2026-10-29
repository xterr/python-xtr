"""IdType: the primary key a new entity gets, and the one an existing entity has."""

from __future__ import annotations

from enum import StrEnum, unique

__all__ = ["IdType"]


@unique
class IdType(StrEnum):
    """An entity's primary key, chosen with ``--id``, which picks its base class.

    ``uuid`` keys are random UUIDs, ``uuid7`` time-ordered ones — friendlier
    to an index — and ``bigint`` an auto-incremented integer. The audited
    bases add ``created_at`` and ``updated_at`` beside the key.
    """

    UUID = "uuid"
    UUID7 = "uuid7"
    BIGINT = "bigint"

    def base(self, *, audit: bool) -> str:
        """Return the name, in ``advanced_alchemy.base``, of the base class with this key."""
        prefix = {IdType.UUID: "UUID", IdType.UUID7: "UUIDv7", IdType.BIGINT: "BigInt"}[self]
        return f"{prefix}{'Audit' if audit else ''}Base"

    @property
    def python_type(self) -> tuple[str, str]:
        """The module and name of the type a column referring to this key holds.

        ``("builtins", "int")`` for an integer key: nothing to import.
        """
        if self is IdType.BIGINT:
            return ("builtins", "int")
        return ("uuid", "UUID")

    @classmethod
    def of_bases(cls, bases: tuple[str, ...]) -> IdType | None:
        """Return the key of a class deriving from ``bases``; ``None`` when none tells.

        A base is recognised by its name, dotted or not: ``BigIntAuditBase``
        has an integer key, ``UUIDBase`` or ``UUIDv7AuditBase`` a UUID one.
        """
        for base in bases:
            name = base.rsplit(".", 1)[-1]
            if name.startswith("BigInt"):
                return cls.BIGINT
            if name.startswith("UUIDv7"):
                return cls.UUID7
            if name.startswith("UUID"):
                return cls.UUID
        return None
