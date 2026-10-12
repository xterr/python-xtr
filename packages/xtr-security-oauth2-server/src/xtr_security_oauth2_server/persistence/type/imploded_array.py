"""A list of value objects kept in one column, space-separated."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar

from sqlalchemy.types import TypeDecorator
from typing_extensions import override

if TYPE_CHECKING:
    from sqlalchemy import Dialect

__all__ = ["ImplodedArray"]

_ValueT = TypeVar("_ValueT")

_SEPARATOR = " "
"""What joins the values: the separator the protocol itself uses for scopes."""


class ImplodedArray(TypeDecorator[Sequence[_ValueT]]):
    """Stores a list of value objects as one space-separated string.

    A client's grants, its redirect URIs and the scopes a credential was
    granted are all short lists of values that are only ever read as a whole.
    A table of its own for each would mean a join for every token read and a
    delete for every registration changed; one column means neither, and the
    separator is the one the protocol already writes scopes with, so what is
    stored reads the same as what goes over the wire.

    Empty means absent: a client with no grants and a credential with no scopes
    both store nothing at all, which is why every column of this kind is
    nullable. Reading it back gives an empty list rather than ``None``, so a
    caller never has to tell "none registered" from "nothing stored".

    A subclass says what the stored words become by implementing
    :meth:`convert_database_values`, and declares ``impl`` and
    ``cache_ok = True`` of its own: these types hold no state, so a query using
    one may be cached, but the flag is read off the concrete class and never
    inherited.
    """

    @override
    def process_bind_param(
        self,
        value: Sequence[_ValueT] | None,
        dialect: Dialect,
    ) -> str | None:
        """Join ``value`` with a space, storing nothing when it holds nothing."""
        del dialect
        if value is None or len(value) == 0:
            return None

        return _SEPARATOR.join(str(item) for item in value)

    @override
    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> tuple[_ValueT, ...]:
        """Split what was stored, and make the values of it."""
        del dialect
        if value is None:
            return ()

        return self.convert_database_values(value.split(_SEPARATOR))

    def convert_database_values(self, values: Sequence[str]) -> tuple[_ValueT, ...]:
        """Return the value objects the stored words stand for.

        The one thing a subclass has to say. Called only with a non-empty list,
        so an implementation never has to handle the absent case.

        Raises:
            NotImplementedError: Always; a subclass says what the words become.
        """
        del values

        raise NotImplementedError
