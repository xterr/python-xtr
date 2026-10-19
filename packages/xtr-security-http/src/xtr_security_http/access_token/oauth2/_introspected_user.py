"""Building the user a token introspection response describes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from xtr_security_core.user.oauth2_user import OAuth2User

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["build_user"]

_TRUE_FLAGS: Final = frozenset({"1", "true", "on", "yes"})
"""The spellings a verified flag reads as true."""

_FALSE_FLAGS: Final = frozenset({"0", "false", "off", "no"})
"""The spellings a verified flag reads as false."""

_VERIFIED_FLAGS: Final = ("email_verified", "phone_number_verified")
"""The members a boolean is recognized on, and dropped when it is not."""

_INT_FLAGS: Final = {1: True, 0: False}
"""The numbers a verified flag reads as a boolean, and the boolean each names."""


def build_user(claims: Mapping[str, object]) -> OAuth2User:
    """Build the user the introspection response describes.

    The standard members land on the user's own attributes — the local
    :class:`~xtr_security_core.user.oauth2_user.OAuth2User` speaks the response's
    own spelling — and every other member is kept as an additional claim under
    the name the response carried. Two normalisations run before the user is
    built: an empty string and a null member are dropped, and the two verified
    flags keep only a value that recognisably names a boolean — a string
    ``"false"`` must not arrive as a verified ``True`` the way a naive cast
    would read it, so anything unrecognized is dropped rather than turned into
    a verified flag. A numeric ``updated_at`` becomes the moment it names.
    """
    kept = {key: value for key, value in claims.items() if value is not None and value != ""}
    updated_at = kept.get("updated_at")
    if isinstance(updated_at, (int, float)) and not isinstance(updated_at, bool):
        kept["updated_at"] = datetime.fromtimestamp(updated_at, UTC)
    for flag in _VERIFIED_FLAGS:
        if flag in kept:
            verified = _verified_flag(kept[flag])
            if verified is None:
                del kept[flag]
            else:
                kept[flag] = verified
    # The members are what the authorization server sent, and the user keeps
    # each as it arrived, so the expansion is not narrowed to the claims the
    # constructor types.
    return OAuth2User(**kept)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def _verified_flag(value: object) -> bool | None:
    """Read ``value`` as a verified flag, or ``None`` when it names no boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return _INT_FLAGS.get(value)
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in _TRUE_FLAGS:
            return True
        if lowered in _FALSE_FLAGS:
            return False
    return None
