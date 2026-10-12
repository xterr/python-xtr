"""Carrying parameters to where a browser is being sent.

Two places build that URI: the grants that end an authorization request in a
redirect, and the endpoint that refuses one before any grant is reached. Both
have to echo the ``state`` the client sent — RFC 6749 §4.1.2.1 requires it of
an error response exactly as of a successful one — so the building of it lives
here rather than once in each.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final
from urllib.parse import urlencode

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["NO_PARAMS", "redirect_uri_carrying"]

NO_PARAMS: Final[Mapping[str, str | int | None]] = MappingProxyType({})
"""Nothing to carry, for a caller that only wants the URI back."""


def redirect_uri_carrying(
    uri: str,
    params: Mapping[str, str | int | None] = NO_PARAMS,
    query_delimiter: str = "?",
) -> str:
    """Return ``uri`` carrying ``params``, in its query or in its fragment.

    A parameter whose value is absent is left out rather than sent empty,
    because a client reads ``state=`` as state it never sent.

    Args:
        uri: Where the browser is being sent.
        params: What to carry there.
        query_delimiter: ``?`` to carry them in the query, ``#`` to carry them
            in the fragment — which is what an access token handed straight to
            a browser uses, so it never reaches a server log.
    """
    separator = "&" if query_delimiter in uri else query_delimiter
    given = {name: value for name, value in params.items() if value is not None}

    return f"{uri}{separator}{urlencode(given)}"
