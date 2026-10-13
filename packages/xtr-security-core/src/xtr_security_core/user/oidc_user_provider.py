"""The provider of the users built from an OIDC provider's claims."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError

from .attributes_based_user_provider_interface import AttributesBasedUserProviderInterface
from .oidc_user import OidcUser

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .user_interface import UserInterface

__all__ = ["OidcUserProvider"]

#: The claims that would land on a security-sensitive argument, reduced to
#: lower-cased letters and digits.
_PRIVILEGED_CLAIMS: Final = frozenset({"roles", "useridentifier"})


@final
class OidcUserProvider(AttributesBasedUserProviderInterface):
    """Provides the OIDC users built from the claims returned by an OIDC provider.

    OIDC users are self-contained: the user is built from the claims collected
    during authentication, and returned as-is when refreshed, without any
    external lookup.

    The claims cannot define the security identity nor grant roles: the
    identifier is the one authentication validated, and the roles default to
    ``ROLE_USER``. Use a provider of your own to map claims onto roles, or to
    load the users from your own store.

    This provider cannot serve a feature that loads a user by its identifier
    alone — impersonation, say — as it needs the claims collected during
    authentication.
    """

    __slots__ = ()

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> OidcUser:
        """Build the user ``identifier`` names from the claims in ``attributes``.

        Raises:
            UserNotFoundError: When the claims carry no usable ``sub``.
        """
        claims: Mapping[str, object] = attributes if attributes is not None else {}
        sub = claims.get("sub")
        if not isinstance(sub, str) or sub == "":
            raise UserNotFoundError(
                identifier,
                f'The "{type(self).__qualname__}" provider cannot load a user by its identifier '
                "alone: OIDC users are built from the claims collected during authentication.",
            )

        # The identifier is the one the caller validated, which the OIDC
        # authenticator reads from the claim its firewall configures, and not a
        # claim picked from the attributes.
        return OidcUser.from_claims(
            {"user_identifier": identifier, **_filter_privileged_claims(claims)},
        )

    @override
    async def refresh_user(self, user: UserInterface) -> OidcUser:
        """Return ``user`` as-is: an OIDC user has nothing to reload.

        Raises:
            UnsupportedUserError: When ``user`` is not an OIDC user.
        """
        if not isinstance(user, OidcUser):
            raise UnsupportedUserError(
                f'Instances of "{type(user).__qualname__}" are not supported.',
            )
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Tell whether ``user_class`` is the OIDC user."""
        return user_class is OidcUser


def _filter_privileged_claims(claims: Mapping[str, object]) -> dict[str, object]:
    """Drop any claim that would land on a security-sensitive argument of the user.

    The provider cannot then populate ``roles`` nor override the
    ``user_identifier`` through the claims it is handed — a privilege
    escalation. The claim name is reduced to its letters and digits,
    lower-cased, to also catch the separator and case variants
    :meth:`OidcUser.from_claims` would map onto those arguments.
    """
    return {
        claim: value
        for claim, value in claims.items()
        if re.sub(r"[^a-zA-Z0-9]+", "", claim).lower() not in _PRIVILEGED_CLAIMS
    }
