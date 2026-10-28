"""What a guard is handed to decide whether a transition may be applied."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    # For the type checker only: guards are optional, and this module must import
    # where no security package is installed. Nothing evaluates the annotations
    # below — the guard listener builds a context, no container does — so the
    # rule reading every dataclass's annotations as runtime ones does not apply.
    from xtr_security_core import (  # noqa: TC004 -- nothing evaluates them, see above
        AuthenticationTrustResolverInterface,
        AuthorizationCheckerInterface,
        TokenInterface,
        UserInterface,
    )

__all__ = ["GuardContext"]


@final
@dataclass(frozen=True, slots=True)
class GuardContext:
    """The subject a guard rules on, who is moving it, and what to check them with.

    A guard is a callable taking one of these and answering whether the
    transition may run — at once, or through an awaitable. It reads the
    subject directly, and asks the security services about whoever is moving
    it::

        async def can_publish(context: GuardContext) -> bool:
            return await context.authorization_checker.is_granted("ROLE_EDITOR", context.subject)

    The authorization checker answers asynchronously; the trust resolver, which
    only reads the token, at once.

    Attributes:
        subject: The object the workflow is moving.
        token: The security token of whoever is moving it; ``None`` when no
            one is authenticated.
        user: The token's user; ``None`` without a token.
        role_names: The token's roles and every role they reach through the
            role hierarchy; empty without a token.
        authorization_checker: Tells whether the current token is granted an
            attribute, over a subject or not.
        trust_resolver: Tells how strongly the token was authenticated — fully,
            remembered, recently.
    """

    subject: object
    token: TokenInterface | None
    user: UserInterface | None
    role_names: tuple[str, ...]
    authorization_checker: AuthorizationCheckerInterface
    trust_resolver: AuthenticationTrustResolverInterface
