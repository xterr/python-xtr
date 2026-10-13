"""Where a request goes through, once the option and the environment agree."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["ProxyConfig"]


@final
@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """A proxy to send through, resolved from the option or the environment.

    Attributes:
        url: Where to connect, as a transport and an address —
            ``tcp://host:port`` for a plain proxy, ``ssl://host:port`` for one
            reached over TLS. The port is always there, filled in from the
            scheme when the proxy did not name one, so a client never has to
            guess it.
        auth: The ``Proxy-Authorization`` credential the proxy's user info
            became, or ``None`` when it carried none.
        no_proxy: The hosts to reach directly, in the order they were listed.
            A client checks the host it is about to reach against these before
            using ``url``.
    """

    url: str
    auth: str | None
    no_proxy: tuple[str, ...]
