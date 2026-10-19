"""Reading the scopes an access token was granted, out of the claims it carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = ["extract_scopes", "normalize_scope"]


def extract_scopes(claims: Mapping[str, object], scope_claims: tuple[str, ...]) -> list[str]:
    """Read the granted scopes out of ``claims``, the first claim that reads answering.

    A list is joined the way a space-separated string already spells its
    scopes, its non-string members dropped; a claim that holds neither a
    string nor a list of strings, or one that trims to nothing, falls through
    to the next claim. What the first reading answers is deduplicated, in the
    order it was granted.
    """
    for claim in scope_claims:
        scope = claims.get(claim)
        if isinstance(scope, (list, tuple)):
            items: Iterable[object] = cast("Iterable[object]", scope)
            scope = " ".join(one for one in items if isinstance(one, str))
        if not isinstance(scope, str) or scope.strip() == "":
            continue
        return list(dict.fromkeys(scope.split()))
    return []


def normalize_scope(scope: object) -> list[str]:
    """Turn a scope list or space-separated string into a list of scopes."""
    if isinstance(scope, str):
        return scope.split()
    if isinstance(scope, (list, tuple, set, frozenset)):
        items: Iterable[object] = cast("Iterable[object]", scope)
        return [str(one) for one in items]
    return [str(scope)]
