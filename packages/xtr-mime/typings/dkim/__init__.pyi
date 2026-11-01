from collections.abc import Sequence
from typing import Protocol

class _DnsLookup(Protocol):
    def __call__(self, name: bytes, timeout: int = 5) -> bytes | None: ...

class DKIMException(Exception): ...  # noqa: N818 -- dkimpy's own name.

class DKIM:
    should_not_sign: set[bytes]
    def __init__(self, message: bytes | None = None) -> None: ...
    def sign(
        self,
        selector: bytes,
        domain: bytes,
        privkey: bytes,
        signature_algorithm: bytes | None = None,
        identity: bytes | None = None,
        canonicalize: tuple[bytes, bytes] = ...,
        include_headers: Sequence[bytes] | None = None,
        length: bool = False,
    ) -> bytes: ...

def verify(message: bytes, dnsfunc: _DnsLookup = ..., minkey: int = 1024) -> bool: ...
