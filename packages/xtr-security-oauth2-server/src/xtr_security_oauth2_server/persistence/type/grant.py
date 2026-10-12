"""The column a client's grants are stored in."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import Text
from typing_extensions import override

from xtr_security_oauth2_server.value_object.grant import Grant as GrantValue

from .imploded_array import ImplodedArray

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["Grant"]


@final
class Grant(ImplodedArray[GrantValue]):
    """Stores the grants a client may use, and nothing when it may use any."""

    impl = Text
    cache_ok = True

    @override
    def convert_database_values(self, values: Sequence[str]) -> tuple[GrantValue, ...]:
        """Return a grant per stored word."""
        return tuple(GrantValue(value) for value in values)
