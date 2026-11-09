"""The digest a session keeps of a password, in place of the password itself."""

from __future__ import annotations

import re

from xtr_security_core.user import password_digest


def test_the_digest_matches_the_catalogue_vector() -> None:
    assert password_digest("123456789") == "e3069283"


def test_the_digest_is_eight_lowercase_hex_characters() -> None:
    assert re.fullmatch(r"[0-9a-f]{8}", password_digest("$argon2id$v=19$m=65536$hash"))


def test_a_different_password_has_a_different_digest() -> None:
    assert password_digest("hashed") != password_digest("rehashed")
