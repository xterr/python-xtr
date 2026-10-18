"""Reading which denied attribute a fresh authentication could grant.

A recency check — ``IS_AUTHENTICATED_RECENTLY`` and its stricter sibling —
refuses a caller who authenticated too long ago, but a fresh proof would
satisfy it, so the voter that denies one asks the firewall for exactly that:
a re-authentication. The ask rides the vote, and the exception listener reads
it back off the decision the denial carries, to tell a denial a fresh proof
would grant apart from one it would not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_security_core.authorization.voter.access import Access

if TYPE_CHECKING:
    from xtr_security_core.exception import AccessDeniedError

__all__ = ["get_re_authentication_attribute", "is_safe_method"]

_SAFE_METHODS: Final[frozenset[str]] = frozenset(("GET", "HEAD", "OPTIONS", "TRACE"))
"""The methods a request carrying one cannot change anything with."""


def get_re_authentication_attribute(error: AccessDeniedError) -> str | None:
    """Return the attribute a voter that denied asked a re-authentication for.

    Several attributes are left alone: deciding them at once is on the way
    out, so only a denial of a single attribute is answered with a fresh
    proof. A closure decides its checks apart from the attribute it was
    denied by name, so a closure denial is answered whatever attribute name
    the vote carries; anything else must match the attribute it was denied
    by, so the fresh proof is asked for the very check that failed.

    Args:
        error: The denial, carrying the decision whose votes were cast.

    Returns:
        The attribute a re-authentication could grant, or ``None`` when no
        vote asked for one.
    """
    if error.access_decision is None:
        return None
    attributes = error.attributes
    if len(attributes) != 1:
        return None
    denied = attributes[0]
    checks_apart = callable(denied)
    for vote in error.access_decision.votes:
        attribute = vote.re_authentication_attribute
        if (
            vote.result is Access.DENIED
            and attribute is not None
            and (checks_apart or denied == attribute)
        ):
            return attribute
    return None


def is_safe_method(method: str) -> bool:
    """Tell whether ``method`` is one a request carrying it cannot change anything with."""
    return method.upper() in _SAFE_METHODS
