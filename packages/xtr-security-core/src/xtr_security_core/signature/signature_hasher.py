"""Signs and checks the hashes behind login links and remember-me cookies."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast, final

from xtr_clock import SystemClock

from xtr_security_core.exception import (
    ExpiredSignatureError,
    InvalidArgumentError,
    InvalidSignatureError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_clock import ClockInterface

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["SignatureHasher"]

#: The HMAC part of a hash: the base64 of a 32-byte digest, in the hash alphabet.
_HMAC_LENGTH: Final = 44

#: The hash alphabet: base64 without a character a URL or a cookie would mistreat.
_HASH_ALPHABET: Final = str.maketrans("+/=", "-_~")

#: What a hash covers when the caller binds nothing extra into it.
_NO_PARAMETERS: Final[Mapping[str, str | bool | int | float]] = MappingProxyType({})


@final
class SignatureHasher:
    """Creates and checks the signed hashes behind login links and remember-me cookies.

    A hash covers who it is for (the user's identifier), until when it
    counts (the expiry), the user's signature properties (so a new password
    retires every hash issued before it), and any extra parameters the
    caller binds into it. The text it returns has two parts: an HMAC of all
    of that with a secret, followed by a digest of the covered fields — the
    part that does not depend on the secret, so a hash can be checked
    against the loaded user as well as against a bare identifier.

    Args:
        signature_properties: Attribute names on the user; the hash stops
            verifying when any of them changes.
        secret: The secret, or several to rotate it: the first signs, all of
            them verify.
        clock: The clock reading the current time; the system clock when
            ``None``.

    Raises:
        InvalidArgumentError: When ``secret`` is empty, or a sequence with
            an empty secret in it.
    """

    __slots__: tuple[str, ...] = ("_clock", "_secrets", "_signature_properties")

    _signature_properties: tuple[str, ...]
    _secrets: tuple[str, ...]
    _clock: ClockInterface

    def __init__(
        self,
        signature_properties: Sequence[str],
        secret: str | Sequence[str],
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the covered properties, the secrets, and the clock timing expiry."""
        self._signature_properties = tuple(signature_properties)
        self._secrets = (secret,) if isinstance(secret, str) else tuple(secret)
        if not self._secrets or "" in self._secrets:
            raise InvalidArgumentError("A non-empty secret is required.")
        self._clock = clock if clock is not None else SystemClock()

    def compute_signature_hash(
        self,
        user: UserInterface,
        expires: int,
        parameters: Mapping[str, str | bool | int | float] = _NO_PARAMETERS,
    ) -> str:
        """Compute the hash for ``user``, valid until ``expires``.

        Args:
            user: The user the hash is issued to.
            expires: The expiry, as a Unix timestamp.
            parameters: Extra values bound into the hash.

        Returns:
            The hash: the HMAC of everything covered, followed by the digest
            of the covered fields.
        """
        fields_hash = self._compute_fields_hash(user, parameters)
        payload = (
            f"{fields_hash}:{expires}:{user.get_user_identifier()}{_squash_parameters(parameters)}"
        )
        return self._generate_hash(self._secrets[0], payload) + fields_hash

    def accept_signature_hash(
        self,
        user_identifier: str,
        expires: int,
        signature_hash: str,
        parameters: Mapping[str, str | bool | int | float] = _NO_PARAMETERS,
    ) -> None:
        """Check the hash for a user identifier, before the user is loaded.

        Only the HMAC is checked here — the covered fields cannot be,
        without the user — so this is the check for a flow that must not
        load the user before the hash proves the request sound.

        Args:
            user_identifier: The identifier the hash was issued to.
            expires: The expiry it carries, as a Unix timestamp.
            signature_hash: The hash as presented.
            parameters: The extra values it was bound with.

        Raises:
            ExpiredSignatureError: When the hash is past its expiry.
            InvalidSignatureError: When the hash matches neither the
                parameters nor any of the secrets.
        """
        if expires < int(self._clock.now().timestamp()):
            raise ExpiredSignatureError("Signature has expired.")
        if not self._has_valid_hmac(signature_hash, expires, user_identifier, parameters):
            raise InvalidSignatureError("Invalid or expired signature.")

    def verify_signature_hash(
        self,
        user: UserInterface,
        expires: int,
        signature_hash: str,
        parameters: Mapping[str, str | bool | int | float] = _NO_PARAMETERS,
    ) -> None:
        """Check the hash against the loaded user, covered fields and all.

        Args:
            user: The user the hash claims to be for.
            expires: The expiry it carries, as a Unix timestamp.
            signature_hash: The hash as presented.
            parameters: The extra values it was bound with.

        Raises:
            ExpiredSignatureError: When the hash is past its expiry.
            InvalidSignatureError: When the hash matches neither the user's
                covered fields nor any of the secrets.
        """
        if expires < int(self._clock.now().timestamp()):
            raise ExpiredSignatureError("Signature has expired.")
        fields_hash = self._compute_fields_hash(user, parameters)
        if not _hashes_equal(fields_hash, signature_hash[_HMAC_LENGTH:]) or not (
            self._has_valid_hmac(signature_hash, expires, user.get_user_identifier(), parameters)
        ):
            raise InvalidSignatureError("Invalid or expired signature.")

    def _compute_fields_hash(
        self,
        user: UserInterface,
        parameters: Mapping[str, str | bool | int | float],
    ) -> str:
        """Digest the covered properties and parameters, independently of the secret."""
        fields_hash = hashlib.sha256()
        for property_name in self._signature_properties:
            value = _read_user_attribute(user, property_name)
            text = "" if value is None else _text_of(value, f'The property "{property_name}"')
            fields_hash.update(f":{_encode_value(text)}".encode())
        fields_hash.update(_squash_parameters(parameters).encode("utf-8"))
        return _encode_hash(fields_hash.digest())

    def _has_valid_hmac(
        self,
        signature_hash: str,
        expires: int,
        user_identifier: str,
        parameters: Mapping[str, str | bool | int | float],
    ) -> bool:
        """Tell whether the hash's HMAC part matches under any of the secrets."""
        presented = signature_hash[:_HMAC_LENGTH]
        payload = (
            f"{signature_hash[_HMAC_LENGTH:]}:{expires}:{user_identifier}"
            f"{_squash_parameters(parameters)}"
        )
        return any(
            _hashes_equal(self._generate_hash(secret, payload), presented)
            for secret in self._secrets
        )

    def _generate_hash(self, secret: str, token_value: str) -> str:
        """HMAC ``token_value`` under ``secret``, in the hash alphabet."""
        digest = hmac.new(
            secret.encode("utf-8"),
            token_value.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return _encode_hash(digest)


def _read_user_attribute(user: UserInterface, name: str) -> object:
    """Read the attribute ``name`` off ``user``.

    The covered properties are plain attributes here, read as such; a name
    the user's class does not carry fails the read itself.

    Raises:
        AttributeError: When the user carries no attribute ``name``.
    """
    # A dynamic read is untyped; the cast keeps an Any from flowing into the hash.
    return cast("object", getattr(user, name))


def _text_of(value: object, source: str) -> str:
    """Render ``value`` as the text a signature covers, or refuse it.

    Args:
        value: The value to render.
        source: What the value is, for the error — a property or a parameter.

    Raises:
        InvalidArgumentError: When ``value`` is nothing the hash can render.
    """
    match value:
        case bool():
            return "1" if value else "0"
        case str() | int() | float():
            return str(value)
        case date():
            return value.isoformat()
        case Enum():
            return str(value)
        case _:
            raise InvalidArgumentError(
                f"{source} must be a value that can be cast to a string, "
                f"but {type(value).__name__} was given."
            )


def _squash_parameters(parameters: Mapping[str, str | bool | int | float]) -> str:
    """Render the extra parameters as the single text a signature covers.

    Sorted by key, so the order a caller assembled them in does not change
    what they add up to.
    """
    if not parameters:
        return ""
    parts: list[str] = []
    for key in sorted(parameters):
        text = _text_of(parameters[key], f'The parameter "{key}"')
        parts.append(f":{_encode_value(key)}_{_encode_value(text)}")
    return "".join(parts)


def _encode_value(text: str) -> str:
    """Base64 ``text`` so its own bytes cannot collide with the separators around it."""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _encode_hash(raw: bytes) -> str:
    """Base64 a digest in the hash alphabet, safe for a URL and a cookie."""
    return base64.b64encode(raw).decode("ascii").translate(_HASH_ALPHABET)


def _hashes_equal(expected: str, presented: str) -> bool:
    """Compare two hashes in constant time, whatever the presented one carries.

    The presented half comes from a request, and may carry characters
    outside the alphabet; comparing the encoded bytes keeps the comparison
    answering false instead of failing on them.
    """
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))
