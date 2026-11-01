"""Sign with the run's test key, and read back what a signed message sends."""

from __future__ import annotations

import re
from email.parser import BytesHeaderParser
from typing import TYPE_CHECKING

from tests.support.dkim_keys import DOMAIN, SELECTOR, dkim_key
from xtr_mime.crypto import DkimOptions, DkimSigner

if TYPE_CHECKING:
    from xtr_mime import Message, RawMessage

__all__ = ["field_names", "signed_names", "signer", "tags", "wire"]


def signer(options: DkimOptions | None = None, selector: str = SELECTOR) -> DkimSigner:
    """Return a signer for the test domain, with the run's key."""
    return DkimSigner(dkim_key().pem(), DOMAIN, selector, default_options=options)


def wire(message: RawMessage) -> bytes:
    """Return the bytes ``message`` is sent as."""
    return b"".join(message.to_iterable())


def tags(message: Message) -> dict[str, str]:
    """Return the tags of the first DKIM-Signature of ``message``, whitespace taken out."""
    header = message.get_headers().get("DKIM-Signature")
    assert header is not None
    pairs = (tag.partition("=") for tag in header.get_body_as_string().split(";"))
    return {name.strip(): re.sub(r"\s+", "", value) for name, _, value in pairs}


def field_names(sent: bytes) -> list[str]:
    """Return the names of the header fields of ``sent``, in the order a reader finds them."""
    return BytesHeaderParser().parsebytes(sent).keys()


def signed_names(message: Message) -> list[str]:
    """Return the ``h=`` list of the first DKIM-Signature of ``message``."""
    return [name.strip() for name in tags(message)["h"].split(":")]
