"""The S256 verifier hashes the verifier and compares the base64url of the digest."""

from __future__ import annotations

from xtr_security_oauth2_server_core.code_challenge_verifiers import (
    CodeChallengeVerifierInterface,
)
from xtr_security_oauth2_server_core.code_challenge_verifiers.s256_verifier import S256Verifier

#: RFC 7636 appendix B: the reference verifier and the challenge it hashes to.
#: The challenge is the appendix's own value; a truncated variant of it
#: circulates widely and does not hash from this verifier.
REFERENCE_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
REFERENCE_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

#: A verifier whose digest exercises the two sextets the two base64 alphabets
#: disagree on, so the uri-safe form and the padded form differ as literals.
ALPHABET_VERIFIER = "pkce-d"
ALPHABET_CHALLENGE = "c-lTDTumF2qPGe2hrjGwg-4z4WgTa_DfjIoJ6X6nS1w"
ALPHABET_CHALLENGE_IN_PADDED_BASE64 = "c+lTDTumF2qPGe2hrjGwg+4z4WgTa/DfjIoJ6X6nS1w"


def test_it_declares_the_verifier_contract() -> None:
    assert CodeChallengeVerifierInterface in S256Verifier.__mro__


def test_it_names_the_s256_method() -> None:
    assert S256Verifier().get_method() == "S256"


def test_it_accepts_the_reference_verifier_against_the_reference_challenge() -> None:
    assert S256Verifier().verify_code_challenge(REFERENCE_VERIFIER, REFERENCE_CHALLENGE)


def test_it_refuses_a_challenge_the_verifier_does_not_hash_to() -> None:
    assert not S256Verifier().verify_code_challenge(
        "another-verifier-long-enough-to-pass",
        REFERENCE_CHALLENGE,
    )


def test_it_refuses_the_verifier_offered_as_its_own_challenge() -> None:
    # A client downgrading to plain while naming S256 must not get through.
    assert not S256Verifier().verify_code_challenge(REFERENCE_VERIFIER, REFERENCE_VERIFIER)


def test_it_refuses_a_challenge_carrying_the_base64_padding() -> None:
    # A 32-byte digest encodes to 43 characters plus one `=`; the challenge
    # travels without it, so the padded form is a different string.
    assert not S256Verifier().verify_code_challenge(
        REFERENCE_VERIFIER,
        f"{REFERENCE_CHALLENGE}=",
    )


def test_it_accepts_the_uri_safe_form_of_a_digest_using_both_disputed_sextets() -> None:
    assert S256Verifier().verify_code_challenge(ALPHABET_VERIFIER, ALPHABET_CHALLENGE)


def test_it_refuses_that_same_digest_offered_in_the_padded_base64_alphabet() -> None:
    assert not S256Verifier().verify_code_challenge(
        ALPHABET_VERIFIER,
        ALPHABET_CHALLENGE_IN_PADDED_BASE64,
    )


def test_it_refuses_an_empty_challenge() -> None:
    assert not S256Verifier().verify_code_challenge(REFERENCE_VERIFIER, "")


def test_it_judges_a_challenge_carrying_characters_outside_ascii() -> None:
    # No conforming client sends one, so it must be refused as a mismatch
    # rather than raising and taking the whole token request down.
    assert not S256Verifier().verify_code_challenge(REFERENCE_VERIFIER, "pâssé" * 9)
