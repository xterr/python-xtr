"""``CryptTrait`` seals a payload into a token only its own key reads back."""

from __future__ import annotations

import json

import pytest
from joserfc import jwe
from joserfc.jwk import OctKey

from xtr_security_oauth2_server_core import crypt_trait
from xtr_security_oauth2_server_core.crypt_trait import CryptTrait
from xtr_security_oauth2_server_core.exception import InvalidArgumentError, OAuth2Error

#: Base64url of the 32 bytes `00 01 … 1f`, as the recipe mints one.
RAW_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
RAW_KEY_WITHOUT_PADDING = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
ANOTHER_RAW_KEY = "ZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXp7fH1-f4CBgoM="
RAW_KEY_OF_SIXTEEN_BYTES = "AAECAwQFBgcICQoLDA0ODw=="

PASSWORD = "a-password-of-at-least-32-characters"
ANOTHER_PASSWORD = "a-different-password-of-32-plus-chars"
PASSWORD_OF_EXACTLY_THE_MINIMUM = "x" * 32
PASSWORD_ONE_CHARACTER_TOO_SHORT = "x" * 31

#: What an authorization-code payload looks like once a grant has built it.
PAYLOAD: dict[str, object] = {
    "client_id": "desk-app",
    "auth_code_id": "4a0e1f",
    "scopes": ["profile", "email"],
    "user_id": None,
    "expire_time": 1764950400,
}


class _Holder(CryptTrait):
    """A bare holder of the mixin, as a grant or the server holds it."""


def _sealed_with_raw_key() -> _Holder:
    holder = _Holder()
    holder.set_encryption_key(RAW_KEY, "key")
    return holder


@pytest.fixture
def holder() -> _Holder:
    return _sealed_with_raw_key()


def test_it_reads_back_what_it_sealed_with_a_raw_key(holder: _Holder) -> None:
    assert holder.decrypt(holder.encrypt(PAYLOAD)) == PAYLOAD


def test_it_reads_back_what_it_sealed_with_a_password() -> None:
    holder = _Holder()
    holder.set_encryption_key(PASSWORD, "plain")

    assert holder.decrypt(holder.encrypt(PAYLOAD)) == PAYLOAD


def test_it_seals_into_the_compact_form_of_five_segments(holder: _Holder) -> None:
    assert len(holder.encrypt(PAYLOAD).split(".")) == 5


def test_it_names_direct_encryption_and_the_256_bit_cipher_in_the_header(
    holder: _Holder,
) -> None:
    token = holder.encrypt(PAYLOAD)
    key = OctKey.import_key(bytes(range(32)), parameters={"use": "enc"})

    protected = jwe.decrypt_compact(token, key, algorithms=("dir", "A256GCM")).protected

    assert protected == {"alg": "dir", "enc": "A256GCM"}


def test_two_tokens_of_one_payload_differ(holder: _Holder) -> None:
    # A fresh initialisation vector per token: two codes for the same client
    # and scopes must not be recognisable as the same code.
    assert holder.encrypt(PAYLOAD) != holder.encrypt(PAYLOAD)


def test_a_key_minted_without_padding_reads_the_same_tokens() -> None:
    padded = _sealed_with_raw_key()
    unpadded = _Holder()
    unpadded.set_encryption_key(RAW_KEY_WITHOUT_PADDING, "key")

    assert unpadded.decrypt(padded.encrypt(PAYLOAD)) == PAYLOAD


@pytest.mark.parametrize("segment", [0, 1, 2, 3, 4])
def test_it_refuses_a_token_whose_segment_was_tampered_with(
    holder: _Holder,
    segment: int,
) -> None:
    parts = holder.encrypt(PAYLOAD).split(".")
    parts[segment] = f"A{parts[segment]}"

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(".".join(parts))


def test_it_refuses_a_token_sealed_with_another_raw_key(holder: _Holder) -> None:
    other = _Holder()
    other.set_encryption_key(ANOTHER_RAW_KEY, "key")

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(other.encrypt(PAYLOAD))


def test_it_refuses_a_token_sealed_with_another_password() -> None:
    holder = _Holder()
    holder.set_encryption_key(PASSWORD, "plain")
    other = _Holder()
    other.set_encryption_key(ANOTHER_PASSWORD, "plain")

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(other.encrypt(PAYLOAD))


def test_a_password_and_a_raw_key_of_the_same_text_are_different_keys() -> None:
    # The password is stretched, the raw key is used as it stands, so naming
    # the wrong type in the configuration fails loudly rather than silently.
    stretched = _Holder()
    stretched.set_encryption_key(RAW_KEY, "plain")

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = stretched.decrypt(_sealed_with_raw_key().encrypt(PAYLOAD))


def test_a_token_sealed_before_the_key_was_replaced_is_no_longer_read(
    holder: _Holder,
) -> None:
    token = holder.encrypt(PAYLOAD)
    holder.set_encryption_key(ANOTHER_RAW_KEY, "key")

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(token)


def test_it_refuses_a_string_that_is_not_a_token_at_all(holder: _Holder) -> None:
    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt("not-a-token")


def test_it_chains_the_refusal_from_what_the_token_failed_on(holder: _Holder) -> None:
    with pytest.raises(OAuth2Error) as refusal:
        _ = holder.decrypt("not-a-token")

    assert refusal.value.__cause__ is not None


def test_a_token_that_will_not_open_is_not_blamed_on_the_caller(holder: _Holder) -> None:
    # A key was set and the call was right; what failed is the token, so the
    # refusal is the base error and not the one a caller's own mistake raises.
    with pytest.raises(OAuth2Error) as refusal:
        _ = holder.decrypt("not-a-token")

    assert not isinstance(refusal.value, InvalidArgumentError)


def test_it_refuses_a_token_whose_payload_is_not_json(holder: _Holder) -> None:
    key = OctKey.import_key(bytes(range(32)), parameters={"use": "enc"})
    token = jwe.encrypt_compact(
        {"alg": "dir", "enc": "A256GCM"},
        b"not json at all",
        key,
        algorithms=("dir", "A256GCM"),
    )

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(token)


def test_it_refuses_a_token_whose_payload_is_json_but_not_an_object(
    holder: _Holder,
) -> None:
    key = OctKey.import_key(bytes(range(32)), parameters={"use": "enc"})
    token = jwe.encrypt_compact(
        {"alg": "dir", "enc": "A256GCM"},
        json.dumps(["profile", "email"]).encode("utf-8"),
        key,
        algorithms=("dir", "A256GCM"),
    )

    with pytest.raises(OAuth2Error, match="could not be decrypted"):
        _ = holder.decrypt(token)


def test_it_refuses_a_password_one_character_short_of_the_minimum() -> None:
    with pytest.raises(InvalidArgumentError, match="at least 32 characters"):
        _Holder().set_encryption_key(PASSWORD_ONE_CHARACTER_TOO_SHORT, "plain")


def test_it_accepts_a_password_of_exactly_the_minimum() -> None:
    holder = _Holder()
    holder.set_encryption_key(PASSWORD_OF_EXACTLY_THE_MINIMUM, "plain")

    assert holder.decrypt(holder.encrypt(PAYLOAD)) == PAYLOAD


def test_it_refuses_a_raw_key_outside_the_base64url_alphabet() -> None:
    with pytest.raises(InvalidArgumentError, match="base64url"):
        _Holder().set_encryption_key("not a base64url key!", "key")


def test_it_refuses_a_raw_key_written_in_the_padded_base64_alphabet() -> None:
    # `+` and `/` are the two characters base64url replaces; a key carrying
    # them was minted by the wrong encoder and would silently lose bytes.
    with pytest.raises(InvalidArgumentError, match="base64url"):
        _Holder().set_encryption_key(RAW_KEY.replace("A", "+"), "key")


def test_it_refuses_a_raw_key_that_does_not_decode() -> None:
    with pytest.raises(InvalidArgumentError, match="base64url"):
        _Holder().set_encryption_key("AAAAA", "key")


def test_it_refuses_a_raw_key_of_the_wrong_length() -> None:
    with pytest.raises(InvalidArgumentError, match="32 bytes"):
        _Holder().set_encryption_key(RAW_KEY_OF_SIXTEEN_BYTES, "key")


def test_it_refuses_to_seal_before_a_key_is_set() -> None:
    with pytest.raises(InvalidArgumentError, match="no encryption key"):
        _ = _Holder().encrypt(PAYLOAD)


def test_it_refuses_to_read_before_a_key_is_set() -> None:
    with pytest.raises(InvalidArgumentError, match="no encryption key"):
        _ = _Holder().decrypt("eyJhbGciOiJkaXIifQ...")


def test_it_stretches_a_password_once_however_many_tokens_follow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stretch = crypt_trait._derive_key
    calls = 0

    def counted(password: str) -> bytes:
        nonlocal calls
        calls += 1
        return stretch(password)

    monkeypatch.setattr(crypt_trait, "_derive_key", counted)
    holder = _Holder()
    holder.set_encryption_key(PASSWORD, "plain")

    for _ in range(3):
        _ = holder.decrypt(holder.encrypt(PAYLOAD))

    assert calls == 1


def test_its_repr_tells_a_key_is_set_without_showing_it(holder: _Holder) -> None:
    shown = repr(holder)

    assert "set" in shown
    assert RAW_KEY not in shown
    assert "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8" not in shown


def test_its_repr_tells_when_no_key_is_set() -> None:
    assert "unset" in repr(_Holder())


def test_its_repr_names_the_class_holding_the_key(holder: _Holder) -> None:
    assert "_Holder" in repr(holder)
