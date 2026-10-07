"""Turns configured key material — a PEM, a secret, a JWK, a JWK set — into keys."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, cast

from joserfc import jwk
from joserfc.errors import JoseError
from joserfc.jwk import ECKey, KeySet, OctKey, OKPKey, RSAKey
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader._algorithms import (
    HMAC_ALGORITHMS,
    key_type_for_algorithm,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from joserfc.jwk import DictKey, Key, KeySetSerialization

    from xtr_security_jwt.services.key_loader.additional_public_key import AdditionalPublicKey

__all__ = [
    "HMAC_MIN_SECRET_BYTES",
    "import_additional_keys",
    "import_key",
    "require_hmac_secret_length",
]

_PEM_KEY_CLASSES: Final[dict[str, type[RSAKey | ECKey | OKPKey]]] = {
    "RSA": RSAKey,
    "EC": ECKey,
    "OKP": OKPKey,
}

#: The least a shared secret may be, in bytes, for each HMAC algorithm — the key
#: size RFC 7518 requires: the hash's output length (256, 384 or 512 bits).
HMAC_MIN_SECRET_BYTES: Final[dict[str, int]] = {"HS256": 32, "HS384": 48, "HS512": 64}


def require_hmac_secret_length(algorithm: str, secret: str) -> None:
    """Refuse an HMAC secret shorter than ``algorithm`` requires.

    ``HS256``, ``HS384`` and ``HS512`` demand a secret at least as long as the
    hash they use — 32, 48 and 64 bytes — so a short, guessable secret cannot
    weaken the signature. A non-HMAC algorithm has no such rule and passes.

    Raises:
        InvalidConfigurationError: When the secret is shorter than the minimum.
    """
    minimum = HMAC_MIN_SECRET_BYTES.get(algorithm)
    if minimum is None:
        return
    length = len(secret.encode("utf-8"))
    if length < minimum:
        # Imported on the error path, not at module scope: this is a plain
        # library service, and importing xtr_security.bundle eagerly would pull
        # the family's whole bundle-wiring module in just to raise one error,
        # coupling a class that must work without a container to the bundle.
        from xtr_security.bundle import InvalidConfigurationError  # noqa: PLC0415

        raise InvalidConfigurationError(
            f"The {algorithm} signing secret must be at least {minimum} bytes, "
            f"but the configured secret is {length}. Mint a longer secret.",
        )


def import_key(material: str, algorithm: str, passphrase: str | None) -> Key:
    """Import ``material`` as the one key ``algorithm`` signs or verifies with.

    Raises:
        InvalidArgumentError: When the material cannot be read as such a key.
        InvalidConfigurationError: When an HMAC secret is shorter than the
            algorithm requires.
    """
    if algorithm in HMAC_ALGORITHMS:
        require_hmac_secret_length(algorithm, material)
        return OctKey.import_key(material)
    key_type = key_type_for_algorithm(algorithm)
    key_class = _PEM_KEY_CLASSES[key_type]
    password = passphrase.encode("utf-8") if passphrase else None
    try:
        return key_class.import_key(material, password=password)
    except (JoseError, ValueError, TypeError) as error:
        raise InvalidArgumentError(
            f"The key material could not be read as a {key_type} key: {error}",
        ) from error


def import_additional_keys(
    extra: AdditionalPublicKey,
    algorithm: str,
    passphrase: str | None,
) -> list[Key]:
    """Import every key ``extra`` holds — a JWK set, a single JWK, or one PEM.

    A deployment publishes an extra verifying key either as a PEM or as the JWK
    set ``jwt:generate-keypair`` writes; a set holds several keys, each carrying
    its own ``kid``, and only the ones of the algorithm's type can verify a
    token, so a set published alongside keys of other types is read, not refused.

    Raises:
        InvalidArgumentError: Naming the key, when its material is not readable
            JSON, holds no key of the algorithm's type, or cannot be read at all.
    """
    text = extra.material.strip()
    try:
        if not text.startswith("{"):
            return [import_key(extra.material, algorithm, passphrase)]
        return _import_json_keys(text, algorithm, extra.key_id)
    except InvalidArgumentError as error:
        raise InvalidArgumentError(
            f"The additional public key {extra.key_id!r} could not be read: {error}",
        ) from error


def _import_json_keys(text: str, algorithm: str, key_id: str) -> list[Key]:
    """Import a JWK or a JWK set from ``text``, keeping the algorithm's key type.

    Raises:
        InvalidArgumentError: When the text is not a readable JWK document, or
            holds no key of the type the algorithm needs.
        InvalidConfigurationError: When a shared secret the document publishes is
            shorter than the algorithm requires.
    """
    try:
        document = cast("object", json.loads(text))
    except ValueError as error:
        raise InvalidArgumentError(f"the material is not readable JSON: {error}") from error
    if not isinstance(document, dict):
        raise InvalidArgumentError("the material is not a JSON object.")
    entries = cast("dict[str, object]", document)
    key_type = key_type_for_algorithm(algorithm)
    keys = _read_jwk_document(entries)
    matching = [key for key in keys if key.key_type == key_type]
    if not matching:
        raise InvalidArgumentError(f"it holds no {key_type} key, which {algorithm} needs.")
    _require_published_secret_length(matching, algorithm, key_id)
    return matching


def _require_published_secret_length(keys: Sequence[Key], algorithm: str, key_id: str) -> None:
    """Refuse a shared secret a JWK document publishes that is too short to trust.

    A secret given as text is measured by :func:`require_hmac_secret_length` as it
    is imported; one arriving as a JWK or a JWK set is the same secret in another
    wrapping and meets the same floor, so a two-byte ``oct`` key cannot slip in as
    a trusted verifying key and vouch for a forged token.

    Raises:
        InvalidConfigurationError: Naming the key, when a published secret is
            shorter than the algorithm requires.
    """
    minimum = HMAC_MIN_SECRET_BYTES.get(algorithm)
    if minimum is None:
        return
    lengths = (len(key.raw_value) for key in keys if isinstance(key, OctKey))
    short = next((length for length in lengths if length < minimum), None)
    if short is None:
        return
    # Imported on the error path for the reason require_hmac_secret_length states.
    from xtr_security.bundle import InvalidConfigurationError  # noqa: PLC0415

    raise InvalidConfigurationError(
        f"The {algorithm} secret published by the additional public key {key_id!r} must be "
        f"at least {minimum} bytes, but it is {short}. Mint a longer secret.",
    )


def _read_jwk_document(entries: dict[str, object]) -> list[Key]:
    """Read every key a JWK set — or a lone JWK — declares.

    The document comes from a file the deployment named, so its shape is trusted
    to joserfc's own reading of it; only unreadable material is reported here.

    Raises:
        InvalidArgumentError: When joserfc cannot read the document as keys.
    """
    try:
        if "keys" in entries:
            key_set: KeySetSerialization = {"keys": cast("list[DictKey]", entries["keys"])}
            return list(KeySet.import_key_set(key_set))
        return [jwk.import_key(cast("DictKey", entries))]
    except (JoseError, ValueError, TypeError) as error:
        raise InvalidArgumentError(f"joserfc refused the JWK material: {error}") from error
