"""Seals the payloads this server hands to clients and reads them back."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from typing import TYPE_CHECKING, Final, Literal, assert_never, cast

from joserfc import jwe
from joserfc.errors import JoseError
from joserfc.jwk import OctKey
from typing_extensions import override

from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth2_error import OAuth2Error

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["CryptTrait"]

#: Direct encryption with a 256-bit key and AES-GCM: the key is the one this
#: holder carries, so no key is wrapped into the token and the whole payload is
#: authenticated — a token whose ciphertext was edited fails to open at all.
_ALGORITHMS: Final = ("dir", "A256GCM")

#: The domain a password is stretched for. It is fixed rather than random
#: because the derived key has to come out the same on every process that reads
#: the token, and per-deployment uniqueness is the password's job, not a salt's.
_SALT: Final = b"xtr-security-oauth2-server/encryption_key/v1"

#: Enough rounds that guessing a password offline costs real money, paid once
#: when the key is set and never again per token.
_ITERATIONS: Final = 600_000

_KEY_LENGTH: Final = 32
_MINIMUM_PASSWORD_LENGTH: Final = 32

#: Base64url as RFC 4648 section 5 writes it, padding optional.
_BASE64URL: Final = re.compile(r"[A-Za-z0-9_-]+={0,2}")

_NO_KEY: Final = (
    "There is no encryption key set; call set_encryption_key() before sealing or reading a payload."
)
_NOT_BASE64URL: Final = (
    "The encryption key is not base64url; mint it as the base64url of 32 random bytes."
)
_UNREADABLE: Final = (
    "The payload could not be decrypted: the key is wrong or the token was modified."
)


def _derive_key(password: str) -> bytes:
    """Stretch ``password`` into the bytes the cipher takes.

    A password is whatever an operator could remember or paste, so it is run
    through a deliberately slow derivation: the length floor alone would not
    stop a dictionary, and a fast derivation would make guessing the key
    offline as cheap as guessing the password.

    Raises:
        InvalidArgumentError: When the password is shorter than the floor,
            which no amount of stretching makes up for.
    """
    if len(password) < _MINIMUM_PASSWORD_LENGTH:
        raise InvalidArgumentError(
            f"An encryption password must be at least {_MINIMUM_PASSWORD_LENGTH} characters.",
        )
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        _SALT,
        _ITERATIONS,
        dklen=_KEY_LENGTH,
    )


def _decode_key(material: str) -> bytes:
    """Read ``material`` as the base64url of the exact bytes the cipher takes.

    The alphabet is checked before decoding, because a lenient decoder drops
    characters it does not know and would turn a key minted by the wrong
    encoder into a different, silently weaker key.

    Raises:
        InvalidArgumentError: When the material is not base64url, or decodes
            to a different number of bytes than the cipher takes.
    """
    if _BASE64URL.fullmatch(material) is None:
        raise InvalidArgumentError(_NOT_BASE64URL)
    padded = material + "=" * (-len(material) % 4)
    try:
        raw = base64.b64decode(padded, altchars=b"-_", validate=True)
    except binascii.Error as error:
        raise InvalidArgumentError(_NOT_BASE64URL) from error
    if len(raw) != _KEY_LENGTH:
        raise InvalidArgumentError(
            f"An encryption key must decode to {_KEY_LENGTH} bytes, not {len(raw)}.",
        )
    return raw


class CryptTrait:
    """Holds the key this server seals its codes and refresh tokens with.

    An authorization code and a refresh token are state the server hands to a
    client and expects back unaltered: who the code was issued to, which scopes
    it carries, which proof-key challenge redeems it. Sealing that state means
    the server keeps nothing between the two requests, and a client can neither
    read what it holds nor hand back a version it edited.

    Whoever owns the key — the authorization server, a grant — mixes this in and
    calls :meth:`set_encryption_key` once. The key is a password to stretch or
    the bytes themselves; either way the derivation happens there and not per
    token, so sealing and reading cost nothing. Nothing here signs: a signature
    would leave the payload readable, and the payload is the server's business
    alone.
    """

    #: Unset until a key is given, so a holder built with none fails loudly on
    #: first use instead of falling back to a key nobody chose.
    _encryption_key: OctKey | None = None

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Take the key this holder seals and reads payloads with.

        Args:
            key: A password when ``key_type`` is ``plain``, or the base64url of
                the key's bytes when it is ``key``.
            key_type: Which of the two ``key`` is. A password is stretched here
                and only here; bytes are taken as they stand.

        Raises:
            InvalidArgumentError: When the password is too short, or the bytes
                are not base64url of the right length.
        """
        match key_type:
            case "plain":
                raw = _derive_key(key)
            case "key":
                raw = _decode_key(key)
            case _:
                assert_never(key_type)
        self._encryption_key = OctKey.import_key(raw, parameters={"use": "enc"})

    def encrypt(self, payload: Mapping[str, object]) -> str:
        """Seal ``payload`` into a token this holder alone reads back.

        Raises:
            InvalidArgumentError: When no key is set.
        """
        plaintext = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
        return jwe.encrypt_compact(
            {"alg": "dir", "enc": "A256GCM"},
            plaintext,
            self._key(),
            algorithms=_ALGORITHMS,
        )

    def decrypt(self, token: str) -> dict[str, object]:
        """Read back the payload ``token`` carries.

        Every way a token can fail — a wrong key, an edited segment, a payload
        that is not a JSON object — is one refusal, because telling them apart
        would answer a client's questions about the key.

        Raises:
            InvalidArgumentError: When no key is set.
            OAuth2Error: When the token does not open into a payload this
                holder sealed.
        """
        key = self._key()
        try:
            opened = jwe.decrypt_compact(token, key, algorithms=_ALGORITHMS)
        except (JoseError, ValueError) as error:
            raise OAuth2Error(_UNREADABLE) from error
        plaintext = opened.plaintext
        if plaintext is None:
            raise OAuth2Error(_UNREADABLE)
        try:
            payload = cast("object", json.loads(plaintext))
        except (ValueError, UnicodeDecodeError) as error:
            raise OAuth2Error(_UNREADABLE) from error
        if not isinstance(payload, dict):
            raise OAuth2Error(_UNREADABLE)
        return cast("dict[str, object]", payload)

    def _key(self) -> OctKey:
        """Return the key this holder was given.

        Raises:
            InvalidArgumentError: When none was, which is a wiring mistake and
                not something to paper over with a key of our own choosing.
        """
        if self._encryption_key is None:
            raise InvalidArgumentError(_NO_KEY)
        return self._encryption_key

    @override
    def __repr__(self) -> str:
        """Say whether a key is held, never which one.

        Holders of this mixin end up in container dumps and in the frames of a
        traceback, so the key must not be printable from one.
        """
        state = "unset" if self._encryption_key is None else "set"
        return f"<{type(self).__name__} encryption_key={state}>"
