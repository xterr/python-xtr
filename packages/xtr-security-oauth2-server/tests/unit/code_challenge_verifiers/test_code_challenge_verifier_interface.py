"""The verifier interface is runtime-checkable against a conforming verifier."""

from __future__ import annotations

from xtr_security_oauth2_server.code_challenge_verifiers.code_challenge_verifier_interface import (
    CodeChallengeVerifierInterface,
)
from xtr_security_oauth2_server.code_challenge_verifiers.plain_verifier import PlainVerifier
from xtr_security_oauth2_server.code_challenge_verifiers.s256_verifier import S256Verifier


def test_the_plain_verifier_satisfies_the_interface() -> None:
    assert isinstance(PlainVerifier(), CodeChallengeVerifierInterface)


def test_the_s256_verifier_satisfies_the_interface() -> None:
    assert isinstance(S256Verifier(), CodeChallengeVerifierInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), CodeChallengeVerifierInterface)
