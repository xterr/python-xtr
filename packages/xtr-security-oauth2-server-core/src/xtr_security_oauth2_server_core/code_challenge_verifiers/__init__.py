"""The proof-key transforms a code verifier is judged by.

A public client cannot keep a secret, so it proves that the token request comes
from whoever made the authorize request: it sends a challenge up front and the
secret behind it when it redeems the code. One verifier here per transform the
challenge may have been made with.
"""

from __future__ import annotations

from .code_challenge_verifier_interface import CodeChallengeVerifierInterface
from .plain_verifier import PlainVerifier
from .s256_verifier import S256Verifier

__all__ = [
    "CodeChallengeVerifierInterface",
    "PlainVerifier",
    "S256Verifier",
]
