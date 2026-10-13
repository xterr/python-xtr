"""The backend clients a request is actually opened on, one per way of connecting."""

from __future__ import annotations

import ssl
import urllib.request
from typing import TYPE_CHECKING, Final, final

import httpx

from xtr_http_client.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TypeAlias

    _Key: TypeAlias = tuple[object, ...]

__all__ = ["HttpxClients"]

# What `timeout` of `None` means: long enough for a slow server, short enough
# to free the connection. The contract names the number; this is where it is
# turned into one.
_IDLE_TIMEOUT: Final = 60.0

_HTTP_1_1: Final = (None, "1.1")
_HTTP_2: Final = ("2", "2.0")


@final
class HttpxClients:
    """One backend client per set of connection settings, opened when first asked for.

    Two requests can only share a connection pool when they would be happy
    with each other's connections. A proxy, a trust store, a client
    certificate, the protocol version and the deadlines all decide what a
    connection *is*, so each combination of them gets a pool of its own, made
    the first time something asks for it — which is what keeps a client that
    is never used from opening anything.

    The environment's proxy settings are part of that too. The backend reads
    them once, when a pool is made, so they are read here as well and a
    change in them asks for a different pool rather than being ignored.

    Each pool also remembers the addresses that requests pinned their hosts
    to, for as long as the pool lives: a host reached at an address once is
    reached at it again, without asking a resolver a second time.

    ``max_connections`` is the backend's pool-wide ceiling, not a per-host
    one: it counts every connection the pool holds, whichever host each of
    them goes to.
    """

    __slots__ = ("_clients", "_max_connections", "_resolved")

    def __init__(self, max_connections: int) -> None:
        """Open nothing yet.

        Args:
            max_connections: How many connections one pool may hold at once,
                counted across every host it reaches.
        """
        self._max_connections = max_connections
        self._clients: dict[_Key, httpx.AsyncClient] = {}
        self._resolved: dict[_Key, dict[str, str]] = {}

    def for_options(
        self,
        options: Mapping[str, object],
    ) -> tuple[httpx.AsyncClient, dict[str, str]]:
        """Return the pool a request made with ``options`` belongs to.

        Args:
            options: The request's options, merged over the client's
                defaults.

        Returns:
            The pool's client, and the addresses it has had hosts pinned to.

        Raises:
            InvalidArgumentError: When the HTTP version asked for is not one
                this client can send.
        """
        key = _key(options)
        client = self._clients.get(key)
        if client is None:
            client = _build(options, self._max_connections)
            self._clients[key] = client
            self._resolved[key] = {}

        return client, self._resolved[key]

    async def aclose(self) -> None:
        """Close every pool, and with it every connection any of them holds."""
        clients = list(self._clients.values())
        self._clients.clear()
        self._resolved.clear()

        for client in clients:
            await client.aclose()


def _key(options: Mapping[str, object]) -> _Key:
    """What makes two requests able to share a pool."""
    return (
        options.get("proxy"),
        options.get("verify_peer"),
        options.get("verify_host"),
        options.get("cafile"),
        options.get("capath"),
        options.get("local_cert"),
        options.get("local_pk"),
        options.get("passphrase"),
        _wants_http2(options.get("http_version")),
        options.get("timeout"),
        options.get("max_connect_duration"),
        tuple(sorted(urllib.request.getproxies().items())),
    )


def _build(options: Mapping[str, object], max_connections: int) -> httpx.AsyncClient:
    """Open the pool ``options`` asks for."""
    proxy = options.get("proxy")
    timeout = options.get("timeout")
    connect = options.get("max_connect_duration")

    try:
        return httpx.AsyncClient(
            trust_env=True,
            follow_redirects=False,
            http2=_wants_http2(options.get("http_version")),
            limits=httpx.Limits(max_connections=max_connections),
            timeout=httpx.Timeout(
                float(timeout) if isinstance(timeout, (int, float)) else _IDLE_TIMEOUT,
                connect=float(connect) if isinstance(connect, (int, float)) and connect else None,
            ),
            proxy=str(proxy) if proxy else None,
            verify=_verification(options),
        )
    except ImportError as error:
        # The HTTP/2 framing is an optional install, and asking for a version
        # that was never installed is an argument this client cannot honour.
        raise InvalidArgumentError(
            'Option "http_version" of "2" needs the "http2" extra: install xtr-http-client[http2].'
        ) from error


def _wants_http2(version: object) -> bool:
    """Whether ``version`` asks for HTTP/2.

    Raises:
        InvalidArgumentError: When it asks for a version this client cannot
            send. HTTP/1.0 is one of them: nothing here can be made to leave
            out what 1.1 added.
    """
    if version in _HTTP_1_1:
        return False
    if version in _HTTP_2:
        return True

    raise InvalidArgumentError(
        f'Invalid HTTP version "{version}", only "1.1" and "2" can be asked for.'
    )


def _verification(options: Mapping[str, object]) -> ssl.SSLContext | bool:
    """How the peer's certificate is to be checked, as the backend takes it.

    ``True`` and ``False`` are the two plain answers — check with the
    platform's trust store, or check nothing. Anything in between is a
    context, because that is the only place another trust store, a client
    certificate or a name that is not to be matched can be said.
    """
    if not options.get("verify_peer", True):
        return False

    verify_host = bool(options.get("verify_host", True))
    cafile = _text(options.get("cafile"))
    capath = _text(options.get("capath"))
    local_cert = _text(options.get("local_cert"))

    if verify_host and cafile is None and capath is None and local_cert is None:
        return True

    context = ssl.create_default_context(cafile=cafile, capath=capath)
    # Order matters: the hostname check cannot be turned off while the
    # certificate is still being verified against a name.
    context.check_hostname = verify_host
    context.verify_mode = ssl.CERT_REQUIRED

    if local_cert is not None:
        context.load_cert_chain(
            local_cert,
            _text(options.get("local_pk")),
            _text(options.get("passphrase")),
        )

    return context


def _text(value: object) -> str | None:
    """``value`` as text, or ``None`` when it was left out."""
    return value if isinstance(value, str) else None
