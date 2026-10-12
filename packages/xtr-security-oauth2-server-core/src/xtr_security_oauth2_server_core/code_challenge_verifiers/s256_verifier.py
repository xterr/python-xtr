"""The transform that hashes the verifier before it travels."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import final

from typing_extensions import override

from .code_challenge_verifier_interface import CodeChallengeVerifierInterface

__all__ = ["S256Verifier"]


@final
class S256Verifier(CodeChallengeVerifierInterface):
    """Judges an ``S256`` challenge: the uri-safe base64 of the verifier's digest.

    This is the transform a server should require, because the authorize request
    carries only the digest: reading it buys an attacker nothing, since the token
    request has to present the secret it was made from. The encoding drops the
    padding and uses the two uri-safe characters, so the challenge survives a
    query string unescaped.
    """

    __slots__ = ()

    @override
    def get_method(self) -> str:
        """Return ``S256``, the method name a client names this transform by."""
        return "S256"

    @override
    def verify_code_challenge(self, code_verifier: str, code_challenge: str) -> bool:
        """Tell whether ``code_challenge`` is the encoded digest of ``code_verifier``.

        The comparison is constant-time, and runs on bytes, so a challenge
        carrying characters outside ascii is refused rather than raising.
        """
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=")
        return hmac.compare_digest(expected, code_challenge.encode("utf-8"))
