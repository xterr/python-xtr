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

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["has_user_changed"]

# The length a password abbreviated as a crc32c checksum spells — the legacy
# format the carve-out below is written for.
_LEGACY_PASSWORD_LENGTH: Final = 8

# The Castagnoli polynomial, reflected: the one the crc32c checksum is built
# from. A row of the lookup table is the remainder of one byte's every
# possible value under it, built here once rather than per call.
_CRC32C_POLYNOMIAL: Final = 0x82F63B78


def _build_row(index: int) -> int:
    """Return one row of the crc32c table: the remainder of ``index``."""
    crc = index
    for _ in range(8):
        crc = (crc >> 1) ^ (_CRC32C_POLYNOMIAL if crc & 1 else 0)
    return crc


_CRC32C_TABLE: Final = tuple(_build_row(index) for index in range(256))


def _crc32c(text: str) -> str:
    """Return the crc32c checksum of ``text``, as eight lowercase hex characters.

    The checksum of ``"123456789"`` is ``e3069283`` — the one test vector the
    CRC-32C catalogue carries, and what a test pins this implementation to.
    """
    crc = 0xFFFFFFFF
    for byte in text.encode("utf-8"):
        crc = _CRC32C_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return f"{crc ^ 0xFFFFFFFF:08x}"


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
    length that differs is a changed password.

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
                or _crc32c(refreshed_password or "") != original_password
            )
        ):
            return True

    user_roles = {str(role) for role in refreshed_user.get_roles()}
    token_role_names = set(token.get_role_names())
    if len(user_roles) != len(token_role_names) or not user_roles <= token_role_names:
        return True

    return original_user.get_user_identifier() != refreshed_user.get_user_identifier()
