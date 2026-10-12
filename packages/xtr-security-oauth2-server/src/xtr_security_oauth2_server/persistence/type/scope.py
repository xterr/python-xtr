"""The column a list of scopes is stored in."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import Text
from typing_extensions import override

from xtr_security_oauth2_server.value_object.scope import Scope as ScopeValue

from .imploded_array import ImplodedArray

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Scope"]


@final
class Scope(ImplodedArray[ScopeValue]):
    """Stores the scopes a client is registered for, or a credential was granted.

    The stored string is exactly the ``scope`` parameter of the protocol — one
    scope per space — so a column of these is readable without this package.
    """

    impl = Text
    cache_ok = True

    @override
    def convert_database_values(self, values: Sequence[str]) -> tuple[ScopeValue, ...]:
        """Return a scope per stored word."""
        return tuple(ScopeValue(value) for value in values)
