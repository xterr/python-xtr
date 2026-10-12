"""The plain verifier compares the verifier to the challenge as they stand."""

from __future__ import annotations

from xtr_security_oauth2_server.code_challenge_verifiers.code_challenge_verifier_interface import (
    CodeChallengeVerifierInterface,
)
from xtr_security_oauth2_server.code_challenge_verifiers.plain_verifier import PlainVerifier

VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


def test_it_declares_the_verifier_contract() -> None:
    assert CodeChallengeVerifierInterface in PlainVerifier.__mro__


def test_it_names_the_plain_method() -> None:
    assert PlainVerifier().get_method() == "plain"


def test_it_accepts_a_challenge_equal_to_the_verifier() -> None:
    assert PlainVerifier().verify_code_challenge(VERIFIER, VERIFIER)


def test_it_refuses_a_challenge_differing_from_the_verifier() -> None:
    assert not PlainVerifier().verify_code_challenge(VERIFIER, "another-challenge")


def test_it_refuses_a_challenge_that_only_prefixes_the_verifier() -> None:
    # A prefix comparison would hand a client a shorter challenge to guess.
    assert not PlainVerifier().verify_code_challenge(VERIFIER, VERIFIER[:10])


def test_it_refuses_a_challenge_differing_only_in_case() -> None:
    assert not PlainVerifier().verify_code_challenge(VERIFIER, VERIFIER.upper())


def test_it_refuses_an_empty_challenge() -> None:
    assert not PlainVerifier().verify_code_challenge(VERIFIER, "")


def test_it_judges_a_verifier_carrying_characters_outside_ascii() -> None:
    # No conforming client sends one, so it must be refused as a mismatch
    # rather than raising and taking the whole token request down.
    assert not PlainVerifier().verify_code_challenge("pâssé" * 9, VERIFIER)
    assert PlainVerifier().verify_code_challenge("pâssé" * 9, "pâssé" * 9)
