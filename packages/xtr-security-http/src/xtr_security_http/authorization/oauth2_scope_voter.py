"""A voter that grants by the scopes a bearer token carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, cast, final

from typing_extensions import override
from xtr_security_core.authorization.voter.access import Access
from xtr_security_core.authorization.voter.cacheable_voter_interface import CacheableVoterInterface
from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter.vote import Vote

__all__ = ["OAuth2ScopeVoter", "oauth2_scope", "parse_oauth2_scope"]

_PREFIX: Final = "OAUTH2_SCOPE("
_SUFFIX: Final = ")"


def oauth2_scope(*scopes: str) -> str:
    """Build the attribute string that asks for ``scopes``.

    ``oauth2_scope("books:read", "books:write")`` returns
    ``"OAUTH2_SCOPE(books:read books:write)"`` — the attribute an access rule or
    an ``IsGranted`` hands to
    :class:`OAuth2ScopeVoter`.

    Raises:
        InvalidArgumentError: When called with no scopes, which would build an
            attribute that grants any scoped token.
    """
    if not scopes:
        raise InvalidArgumentError("Asking for OAuth2 scopes requires at least one scope.")
    return f"{_PREFIX}{' '.join(scopes)}{_SUFFIX}"


@final
class OAuth2ScopeVoter(CacheableVoterInterface):
    """Grants ``OAUTH2_SCOPE(...)`` when the token carries every scope asked for.

    A bearer token keeps the scopes it was issued with in the ``oauth2_scope``
    attribute — a sequence, or a single space-separated string. This voter reads
    an ``OAUTH2_SCOPE(a b)`` attribute and grants only when every scope in it is
    among the token's. A token that carries no scopes at all is denied: a scope
    request it cannot satisfy is a denial, not a question left to the others —
    abstaining would let it through under an ``allow_if_all_abstain`` manager.
    """

    SCOPE_ATTRIBUTE: ClassVar[str] = "oauth2_scope"

    @staticmethod
    def get_required_scopes(attribute: str) -> tuple[str, ...] | None:
        """Read the scopes an attribute requires, all of which are required.

        The one reader of the scope-request shape: the vote below, the
        exception listener and the insufficient-scope handler all ask it here,
        so they agree on what a scope request is. An attribute that is not
        shaped like one — or names no scopes, which would grant every scoped
        token vacuously — reads as ``None``, so a caller leaves another
        voter's attribute alone and abstains on a malformed one rather than
        silently honouring it.
        """
        if not attribute.startswith(_PREFIX) or not attribute.endswith(_SUFFIX):
            return None
        scopes = attribute[len(_PREFIX) : -len(_SUFFIX)].split()
        return tuple(scopes) or None

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Grant when the token holds every asked-for scope; deny when it falls short."""
        del subject
        result = Access.ABSTAIN
        held = self._held_scopes(token)
        missing: list[str] = []
        for attribute in attributes:
            scopes = parse_oauth2_scope(attribute)
            if scopes is None:
                continue
            result = Access.DENIED
            attribute_missing = [scope for scope in scopes if scope not in held]
            if not attribute_missing:
                if vote is not None:
                    vote.add_reason(f"The access token was granted {', '.join(scopes)}.")
                return Access.GRANTED
            missing.extend(attribute_missing)
        if result is Access.DENIED and vote is not None:
            vote.add_reason(
                f"The access token was not granted {', '.join(dict.fromkeys(missing))}."
            )
        return result

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether ``attribute`` asks for OAuth2 scopes, by its prefix alone.

        The prefix is all a firewall needs to know — that this attribute is
        one this voter reads, not another voter's — so a malformed scope
        request still routes here and is abstained on by the vote, rather
        than being routed nowhere and silently honoured.
        """
        return attribute.startswith(_PREFIX)

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject: scopes are read from the token alone."""
        del subject_type
        return True

    def _held_scopes(self, token: TokenInterface) -> frozenset[str]:
        """Read the scopes the token carries, from a string or a sequence.

        A token with no ``oauth2_scope`` attribute carries no scopes, so it holds
        none of those asked for and the vote denies.
        """
        if not token.has_attribute(self.SCOPE_ATTRIBUTE):
            return frozenset()
        value = token.get_attribute(self.SCOPE_ATTRIBUTE)
        if isinstance(value, str):
            return frozenset(value.split())
        if isinstance(value, (list, tuple, set, frozenset)):
            items = cast("Iterable[object]", value)
            return frozenset(str(scope) for scope in items)
        return frozenset()


def parse_oauth2_scope(attribute: object) -> tuple[str, ...] | None:
    """Read the scopes out of an ``OAUTH2_SCOPE(...)`` attribute, or ``None``.

    The module-level spelling of
    :meth:`OAuth2ScopeVoter.get_required_scopes`, kept for the callers that
    hold a plain attribute rather than the voter: the exception listener, and
    anything an application writes itself. Anything not a string reads as
    ``None``.
    """
    if not isinstance(attribute, str):
        return None
    return OAuth2ScopeVoter.get_required_scopes(attribute)
