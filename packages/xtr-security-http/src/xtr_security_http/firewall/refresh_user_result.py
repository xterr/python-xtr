"""The outcome of refreshing the user a session token carried."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["RefreshUserResult"]


@final
@dataclass(frozen=True, slots=True)
class RefreshUserResult:
    """What came of reloading a session token's user through its providers.

    The token is the outcome when the reload held: the same token, its user
    replaced by the provider's fresh copy. A ``None`` token is a
    deauthentication — no provider vouched for the user — and the rest of the
    fields say why, for the deauthentication event to carry: the reason as a
    sentence, the providers that contributed to the decision, and the
    authentication error a listener gave when one did.

    Attributes:
        token: The refreshed token, or ``None`` when the user was
            deauthenticated.
        deauthentication_reason: A sentence explaining the deauthentication,
            or ``None`` when the token held.
        provider_classes: The classes of the user providers that contributed
            to the deauthentication decision — the ones that detected a
            change in the user, or the ones that could not find it.
        exception: The authentication error a listener of the refreshed-user
            check gave as its reason to deauthenticate.
    """

    token: TokenInterface | None = None
    deauthentication_reason: str | None = None
    provider_classes: tuple[type, ...] = field(default=())
    exception: AuthenticationError | None = None
