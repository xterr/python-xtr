"""The transform that leaves the verifier as it is."""

from __future__ import annotations

import hmac
from typing import final

from typing_extensions import override

from .code_challenge_verifier_interface import CodeChallengeVerifierInterface

__all__ = ["PlainVerifier"]


@final
class PlainVerifier(CodeChallengeVerifierInterface):
    """Judges a ``plain`` challenge, which is the verifier sent as it stands.

    The transform protects nothing on its own — whoever reads the authorize
    request reads the secret the token request will send — so a server keeps it
    only for clients that cannot compute a digest, and refuses it for the rest.
    The comparison is still constant-time: the challenge is a secret for as long
    as the code lives, and a timing answer would hand it over one character at a
    time.
    """

    __slots__ = ()

    @override
    def get_method(self) -> str:
        """Return ``plain``, the method name a client names this transform by."""
        return "plain"

    @override
    def verify_code_challenge(self, code_verifier: str, code_challenge: str) -> bool:
        """Tell whether the verifier and the challenge are the same text.

        Both are compared as their utf-8 bytes, so a verifier carrying
        characters outside ascii — which no conforming client sends — is judged
        and refused rather than refusing the whole request with a type error.
        """
        return hmac.compare_digest(
            code_verifier.encode("utf-8"),
            code_challenge.encode("utf-8"),
        )
