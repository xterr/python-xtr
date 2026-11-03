"""Signing and encrypting messages: who sent them, that nothing changed, who may read them.

:class:`DkimSigner` adds a DKIM signature for a domain; it needs the ``dkim`` extra.
:class:`SMimeSigner` signs a message's body and :class:`SMimeEncrypter` encrypts a whole
message with S/MIME; they need the ``smime`` extra. Importing this package needs neither.
:class:`SignedBody` is the body a DKIM-signed message keeps: the bytes signed.
"""

from __future__ import annotations

from .dkim_options import DkimOptions
from .dkim_signer import DkimSigner
from .s_mime_encrypter import SMimeEncrypter
from .s_mime_signer import SMimeSigner
from .signed_body import SignedBody

__all__ = ["DkimOptions", "DkimSigner", "SMimeEncrypter", "SMimeSigner", "SignedBody"]
