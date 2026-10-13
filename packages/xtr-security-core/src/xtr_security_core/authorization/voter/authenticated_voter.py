"""A voter that grants by how strongly, and how recently, the token is authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_security_core.authentication.token.offline_token_interface import OfflineTokenInterface
from xtr_security_core.exception import InvalidArgumentError

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


class AuthenticatedVoter(CacheableVoterInterface):
    """Votes on the authentication attributes, most restrictive to least restrictive.

    ``IS_AUTHENTICATED_VERY_RECENTLY``, ``IS_AUTHENTICATED_RECENTLY``,
    ``IS_AUTHENTICATED_FULLY``, ``IS_AUTHENTICATED_REMEMBERED`` and
    ``IS_AUTHENTICATED`` read how strongly — and how recently — the token was
    authenticated; ``IS_REMEMBERED`` and ``IS_IMPERSONATOR`` how it came to be;
    ``PUBLIC_ACCESS``, asked alone, is always granted. It defers every question
    of strength to a trust resolver, so it need not know how a token was made.

    No impersonation token exists in this library yet, so ``IS_IMPERSONATOR`` is
    always denied.
    """

    IS_AUTHENTICATED_VERY_RECENTLY: Final[str] = "IS_AUTHENTICATED_VERY_RECENTLY"
    IS_AUTHENTICATED_RECENTLY: Final[str] = "IS_AUTHENTICATED_RECENTLY"
    IS_AUTHENTICATED_FULLY: Final[str] = "IS_AUTHENTICATED_FULLY"
    IS_AUTHENTICATED_REMEMBERED: Final[str] = "IS_AUTHENTICATED_REMEMBERED"
    IS_AUTHENTICATED: Final[str] = "IS_AUTHENTICATED"
    IS_IMPERSONATOR: Final[str] = "IS_IMPERSONATOR"
    IS_REMEMBERED: Final[str] = "IS_REMEMBERED"
    PUBLIC_ACCESS: Final[str] = "PUBLIC_ACCESS"

    #: Most restrictive first: only the reason of the strictest attribute that
    #: failed is reported.
    _DENIAL_REASONS: Final[tuple[tuple[str, str], ...]] = (
        (IS_AUTHENTICATED_VERY_RECENTLY, "The user did not authenticate very recently."),
        (IS_AUTHENTICATED_RECENTLY, "The user is not authenticated recently enough."),
        (IS_AUTHENTICATED_FULLY, "The user is not fully authenticated."),
        (IS_AUTHENTICATED_REMEMBERED, "The user is neither fully authenticated nor remembered."),
        (IS_AUTHENTICATED, "The user is not authenticated."),
        (IS_IMPERSONATOR, "The user is not impersonating another user."),
        (IS_REMEMBERED, "The user is not remembered."),
    )

    __slots__: tuple[str, ...] = ("_authentication_trust_resolver",)

    _authentication_trust_resolver: AuthenticationTrustResolverInterface

    def __init__(self, authentication_trust_resolver: AuthenticationTrustResolverInterface) -> None:
        """Record the resolver that reads a token's authentication strength."""
        self._authentication_trust_resolver = authentication_trust_resolver

    @override
    async def vote(  # noqa: C901, PLR0911, PLR0912 -- one branch per attribute, kept in one place
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Grant when a recognised attribute holds for ``token``, else deny or abstain.

        Raises:
            InvalidArgumentError: When asked about authentication for an
                offline token that carries a user — how that user
                authenticated is unknown.
        """
        del subject
        if (
            len(attributes) == 1
            and isinstance(attributes[0], str)
            and attributes[0] == self.PUBLIC_ACCESS
        ):
            if vote is not None:
                vote.add_reason("Access is public.")
            return Access.GRANTED

        resolver = self._authentication_trust_resolver
        result = Access.ABSTAIN
        for attribute in attributes:
            if not isinstance(attribute, str) or attribute not in _AUTHENTICATION_ATTRIBUTES:
                continue

            # A guest is never authenticated, while how an offline user
            # authenticated is unknown.
            if OfflineTokenInterface in type(token).__mro__ and token.get_user() is not None:
                raise InvalidArgumentError(
                    "Cannot decide on authentication attributes when an offline token is used.",
                )

            result = Access.DENIED

            # Being full fledged is an invariant of the attribute, not part of
            # the strategy: a remembered login is precisely not proof that the
            # user still holds the credentials, so no custom trust resolver
            # gets to grant on one.
            if (
                attribute in (self.IS_AUTHENTICATED_RECENTLY, self.IS_AUTHENTICATED_VERY_RECENTLY)
                and resolver.is_full_fledged(token)
                and self._is_authenticated_recently(token, attribute)
            ):
                if vote is not None:
                    vote.add_reason(
                        "The user authenticated recently."
                        if attribute == self.IS_AUTHENTICATED_RECENTLY
                        else "The user authenticated very recently.",
                    )
                return Access.GRANTED

            if attribute in (
                self.IS_AUTHENTICATED_FULLY,
                self.IS_AUTHENTICATED_REMEMBERED,
            ) and resolver.is_full_fledged(token):
                if vote is not None:
                    vote.add_reason("The user is fully authenticated.")
                return Access.GRANTED

            if attribute == self.IS_AUTHENTICATED_REMEMBERED and resolver.is_remember_me(token):
                if vote is not None:
                    vote.add_reason("The user is remembered.")
                return Access.GRANTED

            if attribute == self.IS_AUTHENTICATED and resolver.is_authenticated(token):
                if vote is not None:
                    vote.add_reason("The user is authenticated.")
                return Access.GRANTED

            if attribute == self.IS_REMEMBERED and resolver.is_remember_me(token):
                if vote is not None:
                    vote.add_reason("The user is remembered.")
                return Access.GRANTED

        if result is Access.DENIED and vote is not None:
            for denied_attribute, reason in self._DENIAL_REASONS:
                if denied_attribute in attributes:
                    vote.add_reason(reason)
                    break

            for attribute in (self.IS_AUTHENTICATED_VERY_RECENTLY, self.IS_AUTHENTICATED_RECENTLY):
                if attribute in attributes:
                    vote.request_re_authentication(attribute)
                    break

        return result

    def _is_authenticated_recently(self, token: TokenInterface, attribute: str) -> bool:
        """Ask the resolver the recency question ``attribute`` stands for."""
        if attribute == self.IS_AUTHENTICATED_RECENTLY:
            return self._authentication_trust_resolver.is_authenticated_recently(token)
        return self._authentication_trust_resolver.is_authenticated_very_recently(token)

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Tell whether ``attribute`` is one this voter reads."""
        return attribute in (*_AUTHENTICATION_ATTRIBUTES, self.PUBLIC_ACCESS)

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Vote on any subject: authentication is read from the token alone."""
        del subject_type
        return True


#: The attributes voted on in the loop; ``PUBLIC_ACCESS`` is answered only alone.
_AUTHENTICATION_ATTRIBUTES: Final = (
    AuthenticatedVoter.IS_AUTHENTICATED_VERY_RECENTLY,
    AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY,
    AuthenticatedVoter.IS_AUTHENTICATED_FULLY,
    AuthenticatedVoter.IS_AUTHENTICATED_REMEMBERED,
    AuthenticatedVoter.IS_AUTHENTICATED,
    AuthenticatedVoter.IS_IMPERSONATOR,
    AuthenticatedVoter.IS_REMEMBERED,
)
