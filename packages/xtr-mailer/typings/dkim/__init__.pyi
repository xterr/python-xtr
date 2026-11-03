from logging import Logger
from typing import Protocol

class _DnsLookup(Protocol):
    def __call__(self, name: bytes, timeout: int = 5) -> bytes | None: ...

def verify(
    message: bytes,
    logger: Logger | None = None,
    dnsfunc: _DnsLookup = ...,
    minkey: int = 1024,
    timeout: int = 5,
    tlsrpt: bool = False,
) -> bool: ...
