"""The timing-equalised load of the user a switch asks to become."""

from __future__ import annotations

import contextlib
import hashlib
import secrets
from typing import TYPE_CHECKING

from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["load_user_timing_equalised"]


def _nonexistent_identifier(username: str) -> str:
    """Return an identifier no provider can know, derived from ``username``.

    Hashed from random bytes — the standard library's SHA-256 where the
    upstream stack hashes its own 128-bit variant, the recorded deviation:
    any unguessable derivation serves, and no hash of it is a dependency
    here.
    """
    return "_" + hashlib.sha256(secrets.token_bytes(8) + username.encode()).hexdigest()


async def load_user_timing_equalised(
    provider: UserProviderInterface,
    username: str,
    current_username: str,
) -> UserInterface:
    """Load ``username``, burning a load beside it so the time tells nothing.

    A load that succeeds is followed by one of a throwaway identifier no
    provider can know, and one that fails is followed by a load of the
    current user, so a switch to a user that exists, a user that does not
    and a user that may not be switched all cost the same time.

    Raises:
        AuthenticationError: Whatever the provider raised for ``username``,
            after the burn.
    """
    try:
        user = await provider.load_user_by_identifier(username)
        # The second load is a timing burn; whatever it raises is the
        # point of it.
        with contextlib.suppress(Exception):
            _ = await provider.load_user_by_identifier(_nonexistent_identifier(username))
    except AuthenticationError:
        _ = await provider.load_user_by_identifier(current_username)
        raise
    return user
