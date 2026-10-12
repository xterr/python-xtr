"""The column a client's redirect URIs are stored in."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy import Text
from typing_extensions import override

from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri as RedirectUriValue

from .imploded_array import ImplodedArray

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["RedirectUri"]


@final
class RedirectUri(ImplodedArray[RedirectUriValue]):
    """Stores the redirect URIs a client may be sent back to.

    A space separates them, which no URI may contain, so what is stored splits
    back the way it went in.
    """

    impl = Text
    cache_ok = True

    @override
    def convert_database_values(self, values: Sequence[str]) -> tuple[RedirectUriValue, ...]:
        """Return a redirect URI per stored word."""
        return tuple(RedirectUriValue(value) for value in values)
