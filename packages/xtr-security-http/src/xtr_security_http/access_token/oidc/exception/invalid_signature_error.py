"""A token's signature did not verify against the keys that should verify it."""

from __future__ import annotations

from typing import ClassVar

from xtr_security_core.exception import AuthenticationError

__all__ = ["InvalidSignatureError"]


class InvalidSignatureError(AuthenticationError):
    """A token's signature did not verify against the keys that should verify it.

    The failure the signature-verification side of the OIDC family names: a
    token signed with another key, or by an issuer whose keys were never
    trusted. Deriving from
    :class:`~xtr_security_core.exception.AuthenticationError` is what lets it
    reach the failure hooks, where it is answered as rejected credentials
    rather than a broken request.
    """

    MESSAGE_KEY: ClassVar[str] = "Invalid token signature."
