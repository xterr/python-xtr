"""What judges a proof-key verifier against the challenge an authorize request left."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["CodeChallengeVerifierInterface"]


@runtime_checkable
class CodeChallengeVerifierInterface(Protocol):
    """Judges a code verifier against the challenge the authorization code carries.

    There is one verifier per transform a client may name in
    ``code_challenge_method``. The authorization server picks the one whose
    :meth:`get_method` equals the method stored with the code, never the one the
    token request asks for, so a client cannot have an ``S256`` challenge judged
    by the ``plain`` transform and redeem a code it only ever saw the challenge
    of.
    """

    def get_method(self) -> str:
        """Return the ``code_challenge_method`` value this verifier answers to."""
        ...

    def verify_code_challenge(self, code_verifier: str, code_challenge: str) -> bool:
        """Tell whether ``code_challenge`` was made from ``code_verifier``."""
        ...
