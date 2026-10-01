"""A voter that grants by how strongly the token is authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from .access import Access
from .cacheable_voter_interface import CacheableVoterInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.authentication_trust_resolver_interface import (
        AuthenticationTrustResolverInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .vote import Vote

__all__ = ["AuthenticatedVoter"]


@final
class AuthenticatedVoter(CacheableVoterInterface):
    """Grants access by the strength of a token's authentication.

    Reads three attributes and nothing else:

    - ``PUBLIC_ACCESS`` — always granted, the way a rule marks a resource open
      to everyone.
    - ``IS_AUTHENTICATED`` — granted when the token carries any user.
    - ``IS_AUTHENTICATED_FULLY`` — granted when the token was fully
      authenticated this unit of work.

    It defers the questions of strength to a trust resolver, so it need not
    know how a token was made.
    """

    IS_AUTHENTICATED: ClassVar[str] = "IS_AUTHENTICATED"
    IS_AUTHENTICATED_FULLY: ClassVar[str] = "IS_AUTHENTICATED_FULLY"
    PUBLIC_ACCESS: ClassVar[str] = "PUBLIC_ACCESS"

    __slots__ = ("_trust_resolver",)

    def __init__(self, trust_resolver: AuthenticationTrustResolverInterface) -> None:
        """Record the resolver that reads a token's authentication strength."""
        self._trust_resolver = trust_resolver

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Grant when a recognised attribute holds for ``token``, else deny or abstain."""
        del subject
        result = Access.ABSTAIN
        for attribute in attributes:
            if not self.supports_attribute(attribute if isinstance(attribute, str) else ""):
                continue
            result = Access.DENIED
            if self._grants(attribute, token):
                return Access.GRANTED
            if vote is not None:
                vote.add_reason(f'The token does not satisfy "{attribute}".')
        return result

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether ``attribute`` is one of the three this voter reads."""
        return attribute in (self.PUBLIC_ACCESS, self.IS_AUTHENTICATED, self.IS_AUTHENTICATED_FULLY)

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject: authentication strength is read from the token alone."""
        del subject_type
        return True

    def _grants(self, attribute: object, token: TokenInterface) -> bool:
        """Decide the one recognised attribute against the token."""
        if attribute == self.PUBLIC_ACCESS:
            return True
        if attribute == self.IS_AUTHENTICATED:
            return self._trust_resolver.is_authenticated(token)
        return self._trust_resolver.is_full_fledged(token)
