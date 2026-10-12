"""The encryption key the tests seal codes and refresh tokens with.

One key, shared by every test that needs one, so a payload a grant sealed reads
back in the test that checks it — which is what an authorization code round
trip is — and so no test has to invent key material of its own.

:func:`seal` and :func:`unseal` are the other half: a refresh token arrives at
the refresh grant as a payload somebody else sealed, so a test has to be able
to seal one, and an authorization code a grant handed out has to be readable to
assert on what it carries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_security_oauth2_server.crypt_trait import CryptTrait

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ENCRYPTION_KEY", "seal", "unseal"]

#: Base64url of the 32 bytes `00 01 … 1f`, as the recipe mints one.
ENCRYPTION_KEY: Final[str] = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="


@final
class _Holder(CryptTrait):
    """Carries the shared key, so a test can seal a payload and read one back."""


_HOLDER: Final[_Holder] = _Holder()
_HOLDER.set_encryption_key(ENCRYPTION_KEY, "key")


def seal(payload: Mapping[str, object]) -> str:
    """Return ``payload`` sealed with the shared key, as a grant would hand it out."""
    return _HOLDER.encrypt(payload)


def unseal(token: str) -> dict[str, object]:
    """Return what ``token`` carries, as the grant reading it back would."""
    return _HOLDER.decrypt(token)
