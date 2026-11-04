from collections.abc import Sequence
from logging import Logger
from typing import Literal, Protocol

class _DnsLookup(Protocol):
    def __call__(self, name: bytes, timeout: int = 5) -> bytes | None: ...

class DKIMException(Exception): ...  # noqa: N818 -- dkimpy's own name.

class DKIM:
    should_not_sign: set[bytes]
    def __init__(
        self,
        message: bytes | None = None,
        logger: Logger | None = None,
        signature_algorithm: bytes = b"rsa-sha256",
        minkey: int = 1024,
        linesep: bytes = b"\r\n",
        debug_content: bool = False,
        timeout: int = 5,
        tlsrpt: bool | Literal["strict"] = False,
    ) -> None: ...
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
    def verify(self, idx: int = 0, dnsfunc: _DnsLookup = ...) -> bool: ...

def verify(
    message: bytes,
    logger: Logger | None = None,
    dnsfunc: _DnsLookup = ...,
    minkey: int = 1024,
    timeout: int = 5,
    tlsrpt: bool | Literal["strict"] = False,
) -> bool: ...
