"""The Standard Webhooks signature scheme, shared by the sender and the receiver.

One module rather than one on each side, because the two must agree byte for byte:
https://www.standardwebhooks.com/. It only makes a signature. Checking one against the
header a request carries is the receiver's job, and it compares with
:func:`hmac.compare_digest`, never ``==``, so the time the comparison takes says nothing
about how much of the signature was right.

Private to this library: the scheme is an implementation detail of the configurator that
emits it and the parser that reads it, and nothing outside has a reason to produce one.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
from typing import Final

__all__ = ["PREFIX", "sign"]

PREFIX: Final = "v1,"
"""The scheme's version marker, which every signature it makes starts with.

A receiver reads it to tell this scheme's entry apart from the others a header may
carry, and a later version of the scheme changes this one constant.
"""

_WHSEC_PREFIX: Final = "whsec_"
"""How the scheme spells a secret whose key is base64 rather than the text itself."""


def sign(message_id: str, timestamp: str, body: bytes, secret: str) -> str:
    """Return the signature for one webhook, prefixed with the scheme's version.

    The id, the timestamp and the body are signed together, each separated by a dot,
    so neither moving a signed body to another delivery nor replaying yesterday's
    delivery keeps the signature valid.

    Args:
        message_id: The webhook's id, as the ``Webhook-Id`` header carries it.
        timestamp: Seconds since the epoch, as the ``Webhook-Timestamp`` header
            carries it — a string, so the signature covers exactly what is sent.
        body: The bytes of the body, signed as they go out: re-encoding a payload
            can reorder keys or respace them, and the receiver signs what arrived.
        secret: The subscriber's secret.

    Returns:
        ``"v1,"`` followed by the base64 of the HMAC-SHA256 digest.
    """
    signed = hmac.new(_key(secret), f"{message_id}.{timestamp}.".encode() + body, hashlib.sha256)

    return PREFIX + base64.b64encode(signed.digest()).decode()


def _key(secret: str) -> bytes:
    """Return the key ``secret`` stands for.

    The scheme writes a secret as base64 behind a ``whsec_`` prefix, so the key is
    bytes that need not be text. A secret written any other way is its own key: a
    receiver configured with a plain string must keep working, and a prefix over
    something that is not base64 is a secret that happens to start with those six
    characters, not a mistake to raise over.
    """
    if not secret.startswith(_WHSEC_PREFIX):
        return secret.encode()

    try:
        return base64.b64decode(secret[len(_WHSEC_PREFIX) :], validate=True)
    except binascii.Error:
        return secret.encode()
