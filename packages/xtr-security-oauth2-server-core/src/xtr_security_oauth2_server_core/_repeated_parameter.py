"""Seeing that a request sent one protocol parameter twice, and refusing it.

RFC 6749 sections 3.1 and 3.2 have it that a request parameter "MUST NOT be
included more than once", and section 5.2 catalogues a request that "includes a
parameter more than once" under ``invalid_request``. Taking the last value
instead would let one hop append a parameter the one before it already sent and
have this server read the appended one.

Whether it can be seen at all depends on what the form or the query string was
parsed into: a plain mapping has already settled on a single value per name,
while the objects a served request hands over keep every value. Two places need
the same reading — the handlers, for every parameter they read, and the
authorization server, for the one parameter that decides which grant reads the
request at all — so it lives here once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MultiValued", "refuse_if_repeated"]


@runtime_checkable
class MultiValued(Protocol):
    """A parameter source that remembers every value sent under a name.

    A plain mapping cannot tell whether a name was sent twice; the objects a
    served request hands over answer for every value under ``getlist``, which
    is the only thing read here.
    """

    def getlist(self, key: str) -> Sequence[object]:
        """Return every value sent under ``key``, in the order they were sent."""
        ...


def refuse_if_repeated(parameter: str, source: object) -> None:
    """Refuse when ``source`` carries ``parameter`` more than once.

    A source that cannot say — a plain mapping, or a body that is no form at
    all — is left alone rather than guessed about.

    Raises:
        OAuthServerError: ``invalid_request`` when the name was sent more than
            once.
    """
    if isinstance(source, MultiValued) and len(source.getlist(parameter)) > 1:
        raise OAuthServerError.invalid_request(parameter)
