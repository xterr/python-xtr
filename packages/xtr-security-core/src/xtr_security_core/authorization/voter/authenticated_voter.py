"""A voter that grants by how strongly the token is authenticated."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, assert_never, final

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


class _Attribute(StrEnum):
    """The three attributes this voter answers, as a closed set to match on."""

    PUBLIC_ACCESS = "PUBLIC_ACCESS"
    IS_AUTHENTICATED = "IS_AUTHENTICATED"
    IS_AUTHENTICATED_FULLY = "IS_AUTHENTICATED_FULLY"


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

    IS_AUTHENTICATED: ClassVar[str] = _Attribute.IS_AUTHENTICATED
    IS_AUTHENTICATED_FULLY: ClassVar[str] = _Attribute.IS_AUTHENTICATED_FULLY
    PUBLIC_ACCESS: ClassVar[str] = _Attribute.PUBLIC_ACCESS

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
            known = _recognise(attribute)
            if known is None:
                continue
            result = Access.DENIED
            if self._grants(known, token):
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

    def _grants(self, attribute: _Attribute, token: TokenInterface) -> bool:
        """Decide the one recognised attribute against the token."""
        match attribute:
            case _Attribute.PUBLIC_ACCESS:
                return True
            case _Attribute.IS_AUTHENTICATED:
                return self._trust_resolver.is_authenticated(token)
            case _Attribute.IS_AUTHENTICATED_FULLY:
                return self._trust_resolver.is_full_fledged(token)
            case _:
                assert_never(attribute)


def _recognise(attribute: object) -> _Attribute | None:
    """Return the attribute as one this voter reads, or ``None`` for any other."""
    if isinstance(attribute, _Attribute):
        return attribute
    if isinstance(attribute, str):
        try:
            return _Attribute(attribute)
        except ValueError:
            return None
    return None
