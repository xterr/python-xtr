"""The key the tests seal authorization codes with, and reading one back.

One key, shared by the server a test builds and by the test itself, so a code
the grant handed out can be opened to assert on what it carries, and a code can
be sealed by hand to hand the grant one it would never have issued.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_security_oauth2_server_core.crypt_trait import CryptTrait

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
