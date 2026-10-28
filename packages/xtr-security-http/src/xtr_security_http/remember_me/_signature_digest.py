"""The digest of a user's signature properties, bound to a stored token value.

A persistent remember-me value is random bytes, but it also carries a digest
of the user's signature properties — the password by default — so a changed
password retires the series even though its random parts never changed. The
digest is separated from the random part by a full stop, which the value's
own base64 alphabet never carries; a stored value without one was written
before the properties were bound, and still counts.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, cast

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["DIGEST_SEPARATOR", "digest_of", "properties_digest", "with_digest"]

#: Separates the random part of a stored value from the digest of the user's
#: signature properties.
DIGEST_SEPARATOR = "."

#: The digest's own, narrower translation of the base64 alphabet: it carries
#: no padding to begin with, so only the two characters a path would mistreat
#: are rewritten.
_DIGEST_ALPHABET = str.maketrans("+/", "-_")

#: The properties whose digest a value carries when the caller configured
#: none — the password alone, the property every password-carrying user
#: exposes.
_DEFAULT_PROPERTIES = ("password",)


def properties_digest(
    user: UserInterface,
    signature_properties: tuple[str, ...] | None,
) -> str | None:
    """Return the digest of the user's signature properties, or ``None``.

    Each property's value is base64-encoded before it is hashed, so its own
    bytes cannot collide with the separators around it — the same reasoning
    as the cookie's own fields. A property the user does not expose is
    skipped while the list is the default one, which keeps a user class
    without any of them working as before; an explicitly configured property
    that is missing is refused, because the caller asked for exactly it.

    Args:
        user: The user whose properties the digest covers.
        signature_properties: The property names, or ``None`` for the
            default list.

    Returns:
        The digest — 24 bytes of SHA-256, base64 in the digest's alphabet —
        or ``None`` when nothing was bound.

    Raises:
        InvalidArgumentError: When an explicitly configured property is
            missing from the user, or holds a value no digest can render.
    """
    is_default_list = signature_properties is None
    properties = _DEFAULT_PROPERTIES if signature_properties is None else signature_properties
    digest = hashlib.sha256()
    is_bound = False
    for property_name in properties:
        if not hasattr(user, property_name):
            if is_default_list:
                continue
            raise InvalidArgumentError(
                f'The user "{type(user).__name__}" carries no property '
                f'"{property_name}" to bind into the token.',
            )
        # A dynamic read is untyped; the cast keeps an Any from flowing into the hash.
        value = cast("object", getattr(user, property_name))
        text = "" if value is None else _text_of(value, f'The property "{property_name}"')
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        digest.update(f":{encoded}".encode())
        is_bound = True
    if not is_bound:
        return None
    # 24 bytes keep the value within the 88 characters the store's column
    # was documented around.
    return base64.b64encode(digest.digest()[:24]).decode("ascii").translate(_DIGEST_ALPHABET)


def digest_of(token_value: str) -> str | None:
    """Return the digest a stored value carries, or ``None`` when it carries none."""
    if DIGEST_SEPARATOR not in token_value:
        return None
    return token_value.partition(DIGEST_SEPARATOR)[2]


def with_digest(token_value: str, digest: str) -> str:
    """Return ``token_value`` carrying ``digest`` behind the separator."""
    return f"{token_value}{DIGEST_SEPARATOR}{digest}"


def _text_of(value: object, source: str) -> str:
    """Render ``value`` as the text a digest covers, or refuse it.

    The same spellings the signature hasher covers its fields with, so a
    property reads the same in a signed value and in a stored one.

    Raises:
        InvalidArgumentError: When ``value`` is nothing a digest can render.
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
                f"but {type(value).__name__} was given.",
            )
