"""A session strategy was asked to move a request that carries no session."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["MissingSessionError"]


class MissingSessionError(SecurityError, RuntimeError):
    """A session strategy found no session on the request it was asked to move.

    The session a strategy moves is the one the request's security state
    carries — the context listener's park, built from the request through
    the session storage. A request whose state holds none reached a
    strategy through a caller that ran no stateful machinery for it, and
    the strategy refuses to guess: rotating a session that does not exist
    would read as protection while protecting nothing. Also a
    :class:`RuntimeError`.
    """
