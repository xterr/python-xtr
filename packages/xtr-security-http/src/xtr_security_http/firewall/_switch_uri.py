"""The URI a switch leaves behind, its own parameters stripped from it."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["uri_without_parameters"]


def uri_without_parameters(uri: str, parameters: Sequence[str]) -> str:
    """Return ``uri`` without ``parameters`` and the values they carry.

    A parameter the switch reads — the username it was asked by, the
    forgery token that vouched for the ask — is removed with its value
    wherever it sits in the query string, so the address a switch
    redirects to names the page it was asked at without naming the switch
    itself: the value stays out of the address bar, the history, the logs
    and the ``Referer`` of the landing page. A removal that leaves the
    path hanging before an ampersand — the stripped parameter was the
    first one after the question mark — mends the join back into a query.

    The strip is written on the URI's text rather than by editing the
    request's query and rebuilding it: a request message is immutable
    here, and the remaining parameters keep the spelling the client sent.
    """
    stripped = uri
    for parameter in parameters:
        stripped = re.sub(rf"[&?]{re.escape(parameter)}=[^&]*", "", stripped)
    return stripped.replace("/&", "/?")
