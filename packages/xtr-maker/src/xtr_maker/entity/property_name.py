"""PropertyName: the check every attribute name ``make:entity`` adds goes through."""

from __future__ import annotations

import keyword
from typing import Final, final

from xtr_maker.exception import InvalidArgumentError

__all__ = ["PropertyName"]

_RESERVED: Final = frozenset(
    {"id", "created_at", "updated_at", "sa_orm_sentinel", "_sentinel", "metadata", "registry"}
)
"""Names the base classes already map, or the declarative layer keeps for itself."""


@final
class PropertyName:
    """Refuses a name an entity attribute cannot have.

    It must be an identifier, not a keyword, not private to the class, and
    not one the base already provides — the key, the audit columns, the
    sentinel column — or the declarative layer reserves (``metadata``,
    ``registry``). Whether the entity already has it is the editor's check.
    """

    __slots__ = ()

    @staticmethod
    def check(name: str) -> str:
        """Return ``name``, stripped, once it may name an attribute.

        Raises:
            InvalidArgumentError: When it may not.
        """
        typed = name.strip()
        if not typed.isidentifier():
            raise InvalidArgumentError(
                f"{typed!r} cannot name a property: it is not an identifier."
            )
        if keyword.iskeyword(typed) or keyword.issoftkeyword(typed):
            raise InvalidArgumentError(f"{typed!r} cannot name a property: it is a Python keyword.")
        if typed.startswith("__"):
            raise InvalidArgumentError(f"{typed!r} cannot name a property: it is name-mangled.")
        if typed in _RESERVED:
            raise InvalidArgumentError(
                f"{typed!r} cannot name a property: the base class already provides it."
            )
        return typed
