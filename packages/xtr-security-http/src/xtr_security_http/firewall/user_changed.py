"""The comparison that decides a refreshed user is another user.

The context listener reloads the user a session token carries through its
providers, and this module answers the one question that reload ends in:
did what came back differ from what was stored? The answer deauthenticates the
token, so every rule that feeds it is a rule about identity, and each is
checked in the order the token itself can settle: a user that compares itself,
a password that changed, roles that were granted or taken away, an identifier
that names someone else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_password_hasher import PasswordAuthenticatedUserInterface
from xtr_security_core.user.equatable_interface import EquatableInterface
from xtr_security_core.user.password_digest import password_digest

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["has_user_changed"]

# The length a password abbreviated as a crc32c checksum spells — the legacy
# format the carve-out below is written for, and the digest a session keeps of
# a password in place of the password.
_LEGACY_PASSWORD_LENGTH: Final = 8


def has_user_changed(
    token: TokenInterface,
    original_user: UserInterface,
    refreshed_user: UserInterface,
) -> bool:
    """Tell whether ``refreshed_user`` is no longer the user ``token`` authenticated.

    A user that knows how to compare itself answers for everyone: the
    password, the roles and the identifier below are what a user without a
    comparison of its own are compared by, and a user with one says so by
    implementing
    :class:`~xtr_security_core.user.equatable_interface.EquatableInterface`.

    The password rule carries one carve-out, kept from the legacy format it
    was written for: a stored password of exactly eight characters that is the
    crc32c checksum of the reloaded one is the *same* password, because that
    is how a password was once abbreviated — so a rehash that changed the
    hash's spelling does not log the user out. A stored password of any other
    length that differs is a changed password. It is also how a session keeps
    a password: the stand-in of a user kept as a snapshot carries the
    :func:`~xtr_security_core.user.password_digest.password_digest` of it, so
    a reload of the same password compares equal.

    The roles are the *token's*, not the original user's: the roles fixed on a
    token describe the authentication the user proved, and a reload that
    grants or takes away a role changes what the token may do even though the
    user it names is the same one.

    Args:
        token: The token the session stored, whose role names the refreshed
            user is weighed against.
        original_user: The user as the session stored it.
        refreshed_user: The user the provider just reloaded.

    Returns:
        Whether the reload changed the user the token carries.
    """
    if isinstance(original_user, EquatableInterface):
        return not original_user.is_equal_to(refreshed_user)

    if isinstance(original_user, PasswordAuthenticatedUserInterface) or isinstance(
        refreshed_user,
        PasswordAuthenticatedUserInterface,
    ):
        if not isinstance(original_user, PasswordAuthenticatedUserInterface) or not isinstance(
            refreshed_user,
            PasswordAuthenticatedUserInterface,
        ):
            # One side stopped carrying a password: the contract the token
            # authenticated under no longer holds.
            return True
        original_password = original_user.get_password()
        refreshed_password = refreshed_user.get_password()
        if (
            original_password is not None
            and refreshed_password != original_password
            and (
                len(original_password) != _LEGACY_PASSWORD_LENGTH
                or password_digest(refreshed_password or "") != original_password
            )
        ):
            return True

    user_roles = {str(role) for role in refreshed_user.get_roles()}
    token_role_names = set(token.get_role_names())
    if len(user_roles) != len(token_role_names) or not user_roles <= token_role_names:
        return True

    return original_user.get_user_identifier() != refreshed_user.get_user_identifier()
